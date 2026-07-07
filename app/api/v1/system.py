"""
API para control del sistema macOS via OSASCRIPT.

Permite interactuar con aplicaciones nativas:
- Calendar, Reminders, Notes, Safari, Contacts
- Sistema: Notificaciones, volumen, modo oscuro
- Finder, Clipboard, Music

SECURITY:
- All endpoints require API key authentication (X-API-Key header)
- Rate limited to prevent abuse
- All operations are logged to Event Store for audit
- Input is sanitized to prevent AppleScript injection
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, field_validator

from app.core.config import settings
from app.core.security import OSAScriptSecurityContext, audit_logger, osascript_security, sanitizer
from app.services.osascript import CalendarEvent, Note, OSAScriptError, Reminder, osascript_service

router = APIRouter(prefix="/system")


# =============================================================================
# SECURITY CHECK
# =============================================================================

def check_osascript_enabled():
    """Check if OSASCRIPT module is enabled"""
    if not settings.osascript_enabled:
        raise HTTPException(
            status_code=503,
            detail="OSASCRIPT module is disabled"
        )


# =============================================================================
# MODELOS (with input validation)
# =============================================================================

class NotificationRequest(BaseModel):
    """Solicitud de notificación"""
    title: str
    message: str
    subtitle: Optional[str] = None
    sound: str = "default"

    @field_validator("title")
    @classmethod
    def validate_title(cls, v):
        return sanitizer.sanitize_string(v, "title")

    @field_validator("message")
    @classmethod
    def validate_message(cls, v):
        return sanitizer.sanitize_string(v, "message")

    @field_validator("subtitle")
    @classmethod
    def validate_subtitle(cls, v):
        if v:
            return sanitizer.sanitize_string(v, "title")
        return v

    @field_validator("sound")
    @classmethod
    def validate_sound(cls, v):
        # Only allow known safe sounds
        allowed_sounds = {"default", "Basso", "Blow", "Bottle", "Frog", "Funk",
                         "Glass", "Hero", "Morse", "Ping", "Pop", "Purr",
                         "Sosumi", "Submarine", "Tink"}
        if v not in allowed_sounds:
            return "default"
        return v


class SpeakRequest(BaseModel):
    """Solicitud de síntesis de voz"""
    text: str
    voice: str = "Samantha"

    @field_validator("text")
    @classmethod
    def validate_text(cls, v):
        return sanitizer.sanitize_string(v, "text")

    @field_validator("voice")
    @classmethod
    def validate_voice(cls, v):
        # Only allow known safe voices
        allowed_voices = {"Samantha", "Alex", "Victoria", "Daniel", "Karen",
                         "Moira", "Tessa", "Veena", "Fiona", "Paulina"}
        if v not in allowed_voices:
            return "Samantha"
        return v


class VolumeRequest(BaseModel):
    """Solicitud de cambio de volumen"""
    level: int

    @field_validator("level")
    @classmethod
    def validate_level(cls, v):
        return max(0, min(100, v))


class CalendarEventRequest(BaseModel):
    """Solicitud de crear evento de calendario"""
    title: str
    start_date: datetime
    end_date: datetime
    location: Optional[str] = None
    notes: Optional[str] = None
    calendar_name: str = "Calendar"

    @field_validator("title", "calendar_name")
    @classmethod
    def validate_title(cls, v):
        return sanitizer.sanitize_string(v, "title")

    @field_validator("location")
    @classmethod
    def validate_location(cls, v):
        if v:
            return sanitizer.sanitize_string(v, "title")
        return v

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, v):
        if v:
            return sanitizer.sanitize_string(v, "body")
        return v


class ReminderRequest(BaseModel):
    """Solicitud de crear recordatorio"""
    name: str
    due_date: Optional[datetime] = None
    notes: Optional[str] = None
    list_name: str = "Reminders"

    @field_validator("name", "list_name")
    @classmethod
    def validate_name(cls, v):
        return sanitizer.sanitize_string(v, "name")

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, v):
        if v:
            return sanitizer.sanitize_string(v, "body")
        return v


class NoteRequest(BaseModel):
    """Solicitud de crear nota"""
    title: str
    body: str
    folder: str = "Notes"

    @field_validator("title", "folder")
    @classmethod
    def validate_title(cls, v):
        return sanitizer.sanitize_string(v, "title")

    @field_validator("body")
    @classmethod
    def validate_body(cls, v):
        return sanitizer.sanitize_string(v, "body")


class URLRequest(BaseModel):
    """Solicitud de abrir URL"""
    url: str
    new_tab: bool = True

    @field_validator("url")
    @classmethod
    def validate_url(cls, v):
        return sanitizer.validate_url(v)


class ClipboardRequest(BaseModel):
    """Solicitud de clipboard"""
    text: str

    @field_validator("text")
    @classmethod
    def validate_text(cls, v):
        return sanitizer.sanitize_string(v, "text")


# =============================================================================
# SISTEMA
# =============================================================================

@router.get("/info")
async def get_system_info(
    request: Request,
    _auth: str = Depends(osascript_security(write=False))
):
    """
    Obtiene información del sistema macOS.

    Requires: API Key (X-API-Key header)
    """
    check_osascript_enabled()
    try:
        info = osascript_service.get_system_info()
        info["frontmost_app"] = osascript_service.get_frontmost_app()
        info["dark_mode"] = osascript_service.is_dark_mode()
        info["volume"] = osascript_service.get_volume()

        await audit_logger.log_operation("get_system_info", request, _auth)
        return info
    except OSAScriptError as e:
        await audit_logger.log_operation("get_system_info", request, _auth, success=False)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/apps")
async def get_running_apps(
    request: Request,
    _auth: str = Depends(osascript_security(write=False))
):
    """
    Lista las aplicaciones en ejecución.

    Requires: API Key (X-API-Key header)
    """
    check_osascript_enabled()
    try:
        apps = osascript_service.get_running_apps()
        await audit_logger.log_operation("get_running_apps", request, _auth)
        return {
            "apps": apps,
            "count": len(apps),
            "frontmost": osascript_service.get_frontmost_app()
        }
    except OSAScriptError as e:
        await audit_logger.log_operation("get_running_apps", request, _auth, success=False)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/notify")
async def send_notification(
    request: Request,
    data: NotificationRequest,
    _auth: str = Depends(osascript_security(write=True))
):
    """
    Envía una notificación del sistema.

    Requires: API Key with write permission
    """
    check_osascript_enabled()
    success = osascript_service.send_notification(
        title=data.title,
        message=data.message,
        subtitle=data.subtitle,
        sound=data.sound
    )

    await audit_logger.log_operation(
        "send_notification", request, _auth,
        success=success,
        details={"title": data.title}
    )

    if success:
        return {"status": "sent", "title": data.title}
    else:
        raise HTTPException(status_code=500, detail="Failed to send notification")


@router.post("/speak")
async def speak_text(
    request: Request,
    data: SpeakRequest,
    _auth: str = Depends(osascript_security(write=True))
):
    """
    Hace que el sistema hable el texto.

    Requires: API Key with write permission
    """
    check_osascript_enabled()
    success = osascript_service.say_text(
        text=data.text,
        voice=data.voice
    )

    await audit_logger.log_operation(
        "speak_text", request, _auth,
        success=success,
        details={"text_length": len(data.text)}
    )

    if success:
        return {"status": "speaking", "text": data.text}
    else:
        raise HTTPException(status_code=500, detail="Failed to speak text")


@router.get("/volume")
async def get_volume(
    request: Request,
    _auth: str = Depends(osascript_security(write=False))
):
    """
    Obtiene el volumen actual del sistema (0-100).

    Requires: API Key (X-API-Key header)
    """
    check_osascript_enabled()
    try:
        level = osascript_service.get_volume()
        await audit_logger.log_operation("get_volume", request, _auth)
        return {"volume": level}
    except OSAScriptError as e:
        await audit_logger.log_operation("get_volume", request, _auth, success=False)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/volume")
async def set_volume(
    request: Request,
    data: VolumeRequest,
    _auth: str = Depends(osascript_security(write=True))
):
    """
    Establece el volumen del sistema (0-100).

    Requires: API Key with write permission
    High-risk operation (may be disabled in production)
    """
    check_osascript_enabled()

    # High-risk operation check
    async with OSAScriptSecurityContext(request, _auth) as ctx:
        if not ctx.is_allowed("set_volume"):
            raise HTTPException(
                status_code=403,
                detail="set_volume is disabled in current configuration"
            )

    success = osascript_service.set_volume(data.level)

    await audit_logger.log_operation(
        "set_volume", request, _auth,
        success=success,
        details={"level": data.level}
    )

    if success:
        return {"status": "set", "volume": data.level}
    else:
        raise HTTPException(status_code=500, detail="Failed to set volume")


@router.post("/dark-mode/toggle")
async def toggle_dark_mode(
    request: Request,
    _auth: str = Depends(osascript_security(write=True))
):
    """
    Alterna el modo oscuro del sistema.

    Requires: API Key with write permission
    High-risk operation (may be disabled in production)
    """
    check_osascript_enabled()

    # High-risk operation check
    async with OSAScriptSecurityContext(request, _auth) as ctx:
        if not ctx.is_allowed("toggle_dark_mode"):
            raise HTTPException(
                status_code=403,
                detail="toggle_dark_mode is disabled in current configuration"
            )

    success = osascript_service.toggle_dark_mode()

    if success:
        is_dark = osascript_service.is_dark_mode()
        await audit_logger.log_operation(
            "toggle_dark_mode", request, _auth,
            details={"new_state": is_dark}
        )
        return {"status": "toggled", "dark_mode": is_dark}
    else:
        await audit_logger.log_operation("toggle_dark_mode", request, _auth, success=False)
        raise HTTPException(status_code=500, detail="Failed to toggle dark mode")


@router.get("/dark-mode")
async def get_dark_mode(
    request: Request,
    _auth: str = Depends(osascript_security(write=False))
):
    """
    Verifica si el modo oscuro está activo.

    Requires: API Key (X-API-Key header)
    """
    check_osascript_enabled()
    try:
        is_dark = osascript_service.is_dark_mode()
        await audit_logger.log_operation("get_dark_mode", request, _auth)
        return {"dark_mode": is_dark}
    except OSAScriptError as e:
        await audit_logger.log_operation("get_dark_mode", request, _auth, success=False)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# CALENDARIO
# =============================================================================

@router.get("/calendar/lists")
async def get_calendars(
    request: Request,
    _auth: str = Depends(osascript_security(write=False))
):
    """
    Lista todos los calendarios disponibles.

    Requires: API Key (X-API-Key header)
    """
    check_osascript_enabled()
    try:
        calendars = osascript_service.get_calendars()
        await audit_logger.log_operation("get_calendars", request, _auth)
        return {"calendars": calendars, "count": len(calendars)}
    except OSAScriptError as e:
        await audit_logger.log_operation("get_calendars", request, _auth, success=False)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/calendar/today")
async def get_today_events(
    request: Request,
    calendar: Optional[str] = None,
    _auth: str = Depends(osascript_security(write=False))
):
    """
    Obtiene los eventos de hoy.

    Requires: API Key (X-API-Key header)
    """
    check_osascript_enabled()
    try:
        # Sanitize calendar name if provided
        if calendar:
            calendar = sanitizer.sanitize_string(calendar, "name")

        events = osascript_service.get_today_events(calendar)
        await audit_logger.log_operation("get_today_events", request, _auth)
        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "events": events,
            "count": len(events)
        }
    except OSAScriptError as e:
        await audit_logger.log_operation("get_today_events", request, _auth, success=False)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calendar/events")
async def create_calendar_event(
    request: Request,
    data: CalendarEventRequest,
    _auth: str = Depends(osascript_security(write=True))
):
    """
    Crea un evento en el calendario.

    Requires: API Key with write permission
    """
    check_osascript_enabled()
    event = CalendarEvent(
        title=data.title,
        start_date=data.start_date,
        end_date=data.end_date,
        location=data.location,
        notes=data.notes,
        calendar_name=data.calendar_name
    )

    success = osascript_service.create_calendar_event(event)

    await audit_logger.log_operation(
        "create_calendar_event", request, _auth,
        success=success,
        details={"title": data.title, "calendar": data.calendar_name}
    )

    if success:
        return {"status": "created", "title": data.title}
    else:
        raise HTTPException(status_code=500, detail="Failed to create event")


# =============================================================================
# RECORDATORIOS
# =============================================================================

@router.get("/reminders/lists")
async def get_reminder_lists(
    request: Request,
    _auth: str = Depends(osascript_security(write=False))
):
    """
    Lista todas las listas de recordatorios.

    Requires: API Key (X-API-Key header)
    """
    check_osascript_enabled()
    try:
        lists = osascript_service.get_reminder_lists()
        await audit_logger.log_operation("get_reminder_lists", request, _auth)
        return {"lists": lists, "count": len(lists)}
    except OSAScriptError as e:
        await audit_logger.log_operation("get_reminder_lists", request, _auth, success=False)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reminders")
async def get_reminders(
    request: Request,
    list_name: Optional[str] = None,
    include_completed: bool = False,
    _auth: str = Depends(osascript_security(write=False))
):
    """
    Obtiene recordatorios.

    Requires: API Key (X-API-Key header)
    """
    check_osascript_enabled()
    try:
        # Sanitize list name if provided
        if list_name:
            list_name = sanitizer.sanitize_string(list_name, "name")

        reminders = osascript_service.get_reminders(list_name, include_completed)
        await audit_logger.log_operation("get_reminders", request, _auth)
        return {"reminders": reminders, "count": len(reminders)}
    except OSAScriptError as e:
        await audit_logger.log_operation("get_reminders", request, _auth, success=False)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reminders")
async def create_reminder(
    request: Request,
    data: ReminderRequest,
    _auth: str = Depends(osascript_security(write=True))
):
    """
    Crea un recordatorio.

    Requires: API Key with write permission
    """
    check_osascript_enabled()
    reminder = Reminder(
        name=data.name,
        due_date=data.due_date,
        notes=data.notes,
        list_name=data.list_name
    )

    success = osascript_service.create_reminder(reminder)

    await audit_logger.log_operation(
        "create_reminder", request, _auth,
        success=success,
        details={"name": data.name, "list": data.list_name}
    )

    if success:
        return {"status": "created", "name": data.name}
    else:
        raise HTTPException(status_code=500, detail="Failed to create reminder")


@router.post("/reminders/{reminder_name}/complete")
async def complete_reminder(
    request: Request,
    reminder_name: str,
    list_name: str = "Reminders",
    _auth: str = Depends(osascript_security(write=True))
):
    """
    Marca un recordatorio como completado.

    Requires: API Key with write permission
    """
    check_osascript_enabled()

    # Sanitize inputs
    reminder_name = sanitizer.sanitize_string(reminder_name, "name")
    list_name = sanitizer.sanitize_string(list_name, "name")

    success = osascript_service.complete_reminder(reminder_name, list_name)

    await audit_logger.log_operation(
        "complete_reminder", request, _auth,
        success=success,
        details={"name": reminder_name, "list": list_name}
    )

    if success:
        return {"status": "completed", "name": reminder_name}
    else:
        raise HTTPException(status_code=500, detail="Failed to complete reminder")


# =============================================================================
# NOTAS
# =============================================================================

@router.get("/notes/folders")
async def get_note_folders(
    request: Request,
    _auth: str = Depends(osascript_security(write=False))
):
    """
    Lista todas las carpetas de notas.

    Requires: API Key (X-API-Key header)
    """
    check_osascript_enabled()
    try:
        folders = osascript_service.get_note_folders()
        await audit_logger.log_operation("get_note_folders", request, _auth)
        return {"folders": folders, "count": len(folders)}
    except OSAScriptError as e:
        await audit_logger.log_operation("get_note_folders", request, _auth, success=False)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/notes")
async def get_notes(
    request: Request,
    folder: Optional[str] = None,
    limit: int = Query(default=10, le=100),
    _auth: str = Depends(osascript_security(write=False))
):
    """
    Obtiene notas.

    Requires: API Key (X-API-Key header)
    """
    check_osascript_enabled()
    try:
        # Sanitize folder name if provided
        if folder:
            folder = sanitizer.sanitize_string(folder, "name")

        notes = osascript_service.get_notes(folder, limit)
        await audit_logger.log_operation("get_notes", request, _auth)
        return {"notes": notes, "count": len(notes)}
    except OSAScriptError as e:
        await audit_logger.log_operation("get_notes", request, _auth, success=False)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/notes")
async def create_note(
    request: Request,
    data: NoteRequest,
    _auth: str = Depends(osascript_security(write=True))
):
    """
    Crea una nota.

    Requires: API Key with write permission
    """
    check_osascript_enabled()
    note = Note(
        title=data.title,
        body=data.body,
        folder=data.folder
    )

    success = osascript_service.create_note(note)

    await audit_logger.log_operation(
        "create_note", request, _auth,
        success=success,
        details={"title": data.title, "folder": data.folder}
    )

    if success:
        return {"status": "created", "title": data.title}
    else:
        raise HTTPException(status_code=500, detail="Failed to create note")


# =============================================================================
# SAFARI
# =============================================================================

@router.get("/safari/tabs")
async def get_safari_tabs(
    request: Request,
    _auth: str = Depends(osascript_security(write=False))
):
    """
    Obtiene las pestañas abiertas en Safari.

    Requires: API Key (X-API-Key header)
    """
    check_osascript_enabled()
    try:
        tabs = osascript_service.get_safari_tabs()
        await audit_logger.log_operation("get_safari_tabs", request, _auth)
        return {"tabs": tabs, "count": len(tabs)}
    except OSAScriptError as e:
        await audit_logger.log_operation("get_safari_tabs", request, _auth, success=False)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/safari/current")
async def get_current_safari_url(
    request: Request,
    _auth: str = Depends(osascript_security(write=False))
):
    """
    Obtiene la URL de la pestaña actual de Safari.

    Requires: API Key (X-API-Key header)
    """
    check_osascript_enabled()
    try:
        url = osascript_service.get_current_safari_url()
        await audit_logger.log_operation("get_current_safari_url", request, _auth)
        return {"url": url}
    except OSAScriptError as e:
        await audit_logger.log_operation("get_current_safari_url", request, _auth, success=False)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/safari/open")
async def open_url_in_safari(
    request: Request,
    data: URLRequest,
    _auth: str = Depends(osascript_security(write=True))
):
    """
    Abre una URL en Safari.

    Requires: API Key with write permission
    High-risk operation (may be disabled in production)
    """
    check_osascript_enabled()

    # High-risk operation check
    async with OSAScriptSecurityContext(request, _auth) as ctx:
        if not ctx.is_allowed("open_url_in_safari"):
            raise HTTPException(
                status_code=403,
                detail="open_url_in_safari is disabled in current configuration"
            )

    success = osascript_service.open_url_in_safari(data.url, data.new_tab)

    await audit_logger.log_operation(
        "open_url_in_safari", request, _auth,
        success=success,
        details={"url": data.url, "new_tab": data.new_tab}
    )

    if success:
        return {"status": "opened", "url": data.url}
    else:
        raise HTTPException(status_code=500, detail="Failed to open URL")


# =============================================================================
# CONTACTOS
# =============================================================================

@router.get("/contacts/search")
async def search_contacts(
    request: Request,
    q: str = Query(..., min_length=2, max_length=100),
    _auth: str = Depends(osascript_security(write=False))
):
    """
    Busca contactos por nombre.

    Requires: API Key (X-API-Key header)
    """
    check_osascript_enabled()
    try:
        # Sanitize query
        q = sanitizer.sanitize_string(q, "query")

        contacts = osascript_service.search_contacts(q)
        await audit_logger.log_operation(
            "search_contacts", request, _auth,
            details={"query": q, "results": len(contacts)}
        )
        return {"query": q, "contacts": contacts, "count": len(contacts)}
    except OSAScriptError as e:
        await audit_logger.log_operation("search_contacts", request, _auth, success=False)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FINDER
# =============================================================================

@router.get("/finder/selection")
async def get_finder_selection(
    request: Request,
    _auth: str = Depends(osascript_security(write=False))
):
    """
    Obtiene los archivos seleccionados en Finder.

    Requires: API Key (X-API-Key header)
    """
    check_osascript_enabled()
    try:
        files = osascript_service.get_selected_files()
        await audit_logger.log_operation("get_finder_selection", request, _auth)
        return {"files": files, "count": len(files)}
    except OSAScriptError as e:
        await audit_logger.log_operation("get_finder_selection", request, _auth, success=False)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/finder/reveal")
async def reveal_in_finder(
    request: Request,
    path: str,
    _auth: str = Depends(osascript_security(write=True))
):
    """
    Revela un archivo/carpeta en Finder.

    Requires: API Key with write permission
    High-risk operation (may be disabled in production)
    """
    check_osascript_enabled()

    # Validate and sanitize path
    try:
        path = sanitizer.validate_path(path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # High-risk operation check
    async with OSAScriptSecurityContext(request, _auth) as ctx:
        if not ctx.is_allowed("reveal_in_finder"):
            raise HTTPException(
                status_code=403,
                detail="reveal_in_finder is disabled in current configuration"
            )

    success = osascript_service.reveal_in_finder(path)

    await audit_logger.log_operation(
        "reveal_in_finder", request, _auth,
        success=success,
        details={"path": path}
    )

    if success:
        return {"status": "revealed", "path": path}
    else:
        raise HTTPException(status_code=500, detail="Failed to reveal in Finder")


# =============================================================================
# CLIPBOARD
# =============================================================================

@router.get("/clipboard")
async def get_clipboard(
    request: Request,
    _auth: str = Depends(osascript_security(write=False))
):
    """
    Obtiene el contenido del portapapeles.

    Requires: API Key (X-API-Key header)
    """
    check_osascript_enabled()
    try:
        content = osascript_service.get_clipboard()
        await audit_logger.log_operation("get_clipboard", request, _auth)
        return {"content": content}
    except OSAScriptError as e:
        await audit_logger.log_operation("get_clipboard", request, _auth, success=False)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clipboard")
async def set_clipboard(
    request: Request,
    data: ClipboardRequest,
    _auth: str = Depends(osascript_security(write=True))
):
    """
    Establece el contenido del portapapeles.

    Requires: API Key with write permission
    High-risk operation (may be disabled in production)
    """
    check_osascript_enabled()

    # High-risk operation check
    async with OSAScriptSecurityContext(request, _auth) as ctx:
        if not ctx.is_allowed("set_clipboard"):
            raise HTTPException(
                status_code=403,
                detail="set_clipboard is disabled in current configuration"
            )

    success = osascript_service.set_clipboard(data.text)

    await audit_logger.log_operation(
        "set_clipboard", request, _auth,
        success=success,
        details={"text_length": len(data.text)}
    )

    if success:
        return {"status": "set"}
    else:
        raise HTTPException(status_code=500, detail="Failed to set clipboard")


# =============================================================================
# MUSIC
# =============================================================================

@router.get("/music/current")
async def get_current_track(
    request: Request,
    _auth: str = Depends(osascript_security(write=False))
):
    """
    Obtiene la canción actual en Music.

    Requires: API Key (X-API-Key header)
    """
    check_osascript_enabled()
    try:
        track = osascript_service.get_current_track()
        await audit_logger.log_operation("get_current_track", request, _auth)
        if track:
            return {"playing": True, "track": track}
        else:
            return {"playing": False, "track": None}
    except OSAScriptError as e:
        await audit_logger.log_operation("get_current_track", request, _auth, success=False)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/music/playpause")
async def music_play_pause(
    request: Request,
    _auth: str = Depends(osascript_security(write=True))
):
    """
    Alterna reproducción en Music.

    Requires: API Key with write permission
    """
    check_osascript_enabled()
    success = osascript_service.music_play_pause()

    await audit_logger.log_operation(
        "music_play_pause", request, _auth,
        success=success
    )

    if success:
        return {"status": "toggled"}
    else:
        raise HTTPException(status_code=500, detail="Failed to toggle playback")
