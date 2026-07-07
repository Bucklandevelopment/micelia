"""
OSASCRIPT Integration: Control del sistema macOS via AppleScript.

Este módulo permite a Micelia interactuar con aplicaciones nativas de macOS:
- Calendar: Leer/crear eventos
- Reminders: Leer/crear recordatorios
- Notes: Leer/crear notas
- Safari: Control del navegador
- System: Notificaciones, volumen, info del sistema
- Contacts: Leer contactos
"""

import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from app.core.logging import log


class OSAScriptError(Exception):
    """Error al ejecutar AppleScript"""
    pass


class AppName(str, Enum):
    """Aplicaciones soportadas"""
    CALENDAR = "Calendar"
    REMINDERS = "Reminders"
    NOTES = "Notes"
    SAFARI = "Safari"
    CONTACTS = "Contacts"
    FINDER = "Finder"
    SYSTEM_EVENTS = "System Events"
    MUSIC = "Music"


@dataclass
class CalendarEvent:
    """Evento de calendario"""
    title: str
    start_date: datetime
    end_date: datetime
    location: Optional[str] = None
    notes: Optional[str] = None
    calendar_name: str = "Calendar"


@dataclass
class Reminder:
    """Recordatorio"""
    name: str
    due_date: Optional[datetime] = None
    notes: Optional[str] = None
    list_name: str = "Reminders"
    completed: bool = False


@dataclass
class Note:
    """Nota"""
    title: str
    body: str
    folder: str = "Notes"


class OSAScriptService:
    """
    Servicio de integración con macOS via osascript.
    Permite control programático de aplicaciones nativas.
    """

    def __init__(self):
        self._verify_osascript()

    def _verify_osascript(self):
        """Verifica que osascript esté disponible"""
        try:
            result = subprocess.run(
                ["which", "osascript"],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                raise OSAScriptError("osascript not found")
        except Exception as e:
            log.warning(f"osascript verification failed: {e}")

    def _run_applescript(self, script: str, timeout: int = 30) -> str:
        """
        Ejecuta un AppleScript y retorna el resultado.

        Args:
            script: Código AppleScript a ejecutar
            timeout: Timeout en segundos

        Returns:
            Salida del script
        """
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=timeout
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip()
                log.error(f"AppleScript error: {error_msg}")
                raise OSAScriptError(error_msg)

            return result.stdout.strip()

        except subprocess.TimeoutExpired:
            raise OSAScriptError(f"Script timed out after {timeout}s")
        except Exception as e:
            raise OSAScriptError(str(e))

    def _run_applescript_file(self, script: str, timeout: int = 30) -> str:
        """Ejecuta AppleScript multilínea"""
        try:
            result = subprocess.run(
                ["osascript"],
                input=script,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip()
                log.error(f"AppleScript error: {error_msg}")
                raise OSAScriptError(error_msg)

            return result.stdout.strip()

        except subprocess.TimeoutExpired:
            raise OSAScriptError(f"Script timed out after {timeout}s")
        except Exception as e:
            raise OSAScriptError(str(e))

    # =========================================================================
    # SISTEMA
    # =========================================================================

    def get_system_info(self) -> Dict[str, Any]:
        """Obtiene información del sistema"""
        script = '''
        tell application "System Events"
            set userName to name of current user
            set computerName to computer name of (system info)
            set cpuType to CPU type of (system info)
        end tell
        return userName & "|" & computerName & "|" & cpuType
        '''
        result = self._run_applescript_file(script)
        parts = result.split("|")

        return {
            "user_name": parts[0] if len(parts) > 0 else None,
            "computer_name": parts[1] if len(parts) > 1 else None,
            "cpu_type": parts[2] if len(parts) > 2 else None
        }

    def get_frontmost_app(self) -> str:
        """Obtiene la aplicación en primer plano"""
        script = '''
        tell application "System Events"
            set frontApp to name of first application process whose frontmost is true
        end tell
        return frontApp
        '''
        return self._run_applescript_file(script)

    def get_running_apps(self) -> List[str]:
        """Lista aplicaciones en ejecución"""
        script = '''
        tell application "System Events"
            set appNames to name of every application process whose background only is false
            set output to ""
            repeat with appName in appNames
                set output to output & appName & "|||"
            end repeat
            return output
        end tell
        '''
        result = self._run_applescript_file(script)
        apps = [app.strip() for app in result.split("|||") if app.strip()]
        return apps

    def send_notification(
        self,
        title: str,
        message: str,
        subtitle: Optional[str] = None,
        sound: str = "default"
    ) -> bool:
        """
        Envía una notificación del sistema.

        Args:
            title: Título de la notificación
            message: Mensaje principal
            subtitle: Subtítulo opcional
            sound: Sonido (default, Basso, Blow, Bottle, Frog, Funk, Glass, Hero, etc.)
        """
        subtitle_part = f'subtitle "{subtitle}"' if subtitle else ""
        script = f'''
        display notification "{message}" with title "{title}" {subtitle_part} sound name "{sound}"
        '''
        try:
            self._run_applescript_file(script)
            log.info(f"Notification sent: {title}")
            return True
        except OSAScriptError as e:
            log.error(f"Failed to send notification: {e}")
            return False

    def say_text(self, text: str, voice: str = "Samantha") -> bool:
        """
        Hace que el sistema hable el texto.

        Args:
            text: Texto a hablar
            voice: Voz a usar (Samantha, Alex, Victoria, etc.)
        """
        script = f'say "{text}" using "{voice}"'
        try:
            self._run_applescript(script)
            return True
        except OSAScriptError:
            return False

    def get_volume(self) -> int:
        """Obtiene el volumen actual (0-100)"""
        script = "output volume of (get volume settings)"
        result = self._run_applescript(script)
        return int(result)

    def set_volume(self, level: int) -> bool:
        """
        Establece el volumen del sistema.

        Args:
            level: Nivel de volumen (0-100)
        """
        level = max(0, min(100, level))
        script = f"set volume output volume {level}"
        try:
            self._run_applescript(script)
            log.info(f"Volume set to {level}")
            return True
        except OSAScriptError:
            return False

    def toggle_dark_mode(self) -> bool:
        """Alterna el modo oscuro del sistema"""
        script = '''
        tell application "System Events"
            tell appearance preferences
                set dark mode to not dark mode
            end tell
        end tell
        '''
        try:
            self._run_applescript_file(script)
            return True
        except OSAScriptError:
            return False

    def is_dark_mode(self) -> bool:
        """Verifica si el modo oscuro está activo"""
        script = '''
        tell application "System Events"
            tell appearance preferences
                return dark mode
            end tell
        end tell
        '''
        result = self._run_applescript_file(script)
        return result.lower() == "true"

    # =========================================================================
    # CALENDARIO
    # =========================================================================

    def get_calendars(self) -> List[str]:
        """Lista todos los calendarios disponibles"""
        script = '''
        tell application "Calendar"
            set calNames to name of every calendar
            set output to ""
            repeat with calName in calNames
                set output to output & calName & "|||"
            end repeat
            return output
        end tell
        '''
        result = self._run_applescript_file(script)
        return [cal.strip() for cal in result.split("|||") if cal.strip()]

    def get_today_events(self, calendar_name: Optional[str] = None) -> List[Dict]:
        """
        Obtiene los eventos de hoy.

        Args:
            calendar_name: Nombre del calendario (opcional, todos si None)
        """
        today = datetime.now().strftime("%Y-%m-%d")
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        # Restringe la búsqueda a un calendario concreto si se indica; si no,
        # recorre todos los calendarios.
        if calendar_name:
            cal_source = f'{{calendar "{calendar_name}"}}'
        else:
            cal_source = "calendars"

        script = f'''
        tell application "Calendar"
            set todayStart to date "{today}"
            set todayEnd to date "{tomorrow}"
            set eventList to {{}}

            repeat with cal in {cal_source}
                set calEvents to (every event of cal whose start date ≥ todayStart and start date < todayEnd)
                repeat with evt in calEvents
                    set eventInfo to summary of evt & "|" & (start date of evt as string) & "|" & (end date of evt as string) & "|" & (location of evt as string)
                    set end of eventList to eventInfo
                end repeat
            end repeat

            return eventList as text
        end tell
        '''
        try:
            result = self._run_applescript_file(script)
            events = []
            if result:
                for event_str in result.split(", "):
                    parts = event_str.split("|")
                    if len(parts) >= 3:
                        events.append({
                            "title": parts[0],
                            "start": parts[1],
                            "end": parts[2],
                            "location": parts[3] if len(parts) > 3 else None
                        })
            return events
        except OSAScriptError:
            return []

    def create_calendar_event(self, event: CalendarEvent) -> bool:
        """
        Crea un evento en el calendario.

        Args:
            event: Datos del evento
        """
        start_str = event.start_date.strftime("%B %d, %Y %I:%M %p")
        end_str = event.end_date.strftime("%B %d, %Y %I:%M %p")

        location_part = f'set location of newEvent to "{event.location}"' if event.location else ""
        notes_part = f'set description of newEvent to "{event.notes}"' if event.notes else ""

        script = f'''
        tell application "Calendar"
            tell calendar "{event.calendar_name}"
                set newEvent to make new event with properties {{summary:"{event.title}", start date:date "{start_str}", end date:date "{end_str}"}}
                {location_part}
                {notes_part}
            end tell
        end tell
        '''
        try:
            self._run_applescript_file(script)
            log.info(f"Calendar event created: {event.title}")
            return True
        except OSAScriptError as e:
            log.error(f"Failed to create event: {e}")
            return False

    # =========================================================================
    # RECORDATORIOS
    # =========================================================================

    def get_reminder_lists(self) -> List[str]:
        """Lista todas las listas de recordatorios"""
        script = '''
        tell application "Reminders"
            set listNames to name of every list
            set output to ""
            repeat with listName in listNames
                set output to output & listName & "|||"
            end repeat
            return output
        end tell
        '''
        result = self._run_applescript_file(script)
        return [lst.strip() for lst in result.split("|||") if lst.strip()]

    def get_reminders(self, list_name: Optional[str] = None, include_completed: bool = False) -> List[Dict]:
        """
        Obtiene recordatorios.

        Args:
            list_name: Nombre de la lista (opcional)
            include_completed: Incluir completados
        """
        completed_filter = "" if include_completed else "whose completed is false"

        if list_name:
            script = f'''
            tell application "Reminders"
                set reminderList to list "{list_name}"
                set rems to every reminder of reminderList {completed_filter}
                set remInfo to {{}}
                repeat with rem in rems
                    set info to name of rem & "|" & (due date of rem as string) & "|" & (completed of rem as string)
                    set end of remInfo to info
                end repeat
                return remInfo as text
            end tell
            '''
        else:
            script = f'''
            tell application "Reminders"
                set remInfo to {{}}
                repeat with lst in lists
                    set rems to every reminder of lst {completed_filter}
                    repeat with rem in rems
                        set info to name of rem & "|" & (due date of rem as string) & "|" & (completed of rem as string)
                        set end of remInfo to info
                    end repeat
                end repeat
                return remInfo as text
            end tell
            '''

        try:
            result = self._run_applescript_file(script)
            reminders = []
            if result:
                for rem_str in result.split(", "):
                    parts = rem_str.split("|")
                    if len(parts) >= 1:
                        reminders.append({
                            "name": parts[0],
                            "due_date": parts[1] if len(parts) > 1 else None,
                            "completed": parts[2].lower() == "true" if len(parts) > 2 else False
                        })
            return reminders
        except OSAScriptError:
            return []

    def create_reminder(self, reminder: Reminder) -> bool:
        """
        Crea un recordatorio.

        Args:
            reminder: Datos del recordatorio
        """
        due_part = ""
        if reminder.due_date:
            due_str = reminder.due_date.strftime("%B %d, %Y %I:%M %p")
            due_part = f', due date:date "{due_str}"'

        notes_part = f', body:"{reminder.notes}"' if reminder.notes else ""

        script = f'''
        tell application "Reminders"
            tell list "{reminder.list_name}"
                make new reminder with properties {{name:"{reminder.name}"{due_part}{notes_part}}}
            end tell
        end tell
        '''
        try:
            self._run_applescript_file(script)
            log.info(f"Reminder created: {reminder.name}")
            return True
        except OSAScriptError as e:
            log.error(f"Failed to create reminder: {e}")
            return False

    def complete_reminder(self, reminder_name: str, list_name: str = "Reminders") -> bool:
        """Marca un recordatorio como completado"""
        script = f'''
        tell application "Reminders"
            tell list "{list_name}"
                set completed of (first reminder whose name is "{reminder_name}") to true
            end tell
        end tell
        '''
        try:
            self._run_applescript_file(script)
            log.info(f"Reminder completed: {reminder_name}")
            return True
        except OSAScriptError:
            return False

    # =========================================================================
    # NOTAS
    # =========================================================================

    def get_note_folders(self) -> List[str]:
        """Lista todas las carpetas de notas"""
        script = '''
        tell application "Notes"
            set folderNames to name of every folder
            set output to ""
            repeat with folderName in folderNames
                set output to output & folderName & "|||"
            end repeat
            return output
        end tell
        '''
        result = self._run_applescript_file(script)
        return [f.strip() for f in result.split("|||") if f.strip()]

    def get_notes(self, folder_name: Optional[str] = None, limit: int = 10) -> List[Dict]:
        """
        Obtiene notas.

        Args:
            folder_name: Nombre de la carpeta (opcional)
            limit: Límite de notas a obtener
        """
        if folder_name:
            script = f'''
            tell application "Notes"
                set noteList to notes of folder "{folder_name}"
                set noteInfo to {{}}
                set counter to 0
                repeat with n in noteList
                    if counter < {limit} then
                        set info to name of n & "|" & (creation date of n as string)
                        set end of noteInfo to info
                        set counter to counter + 1
                    end if
                end repeat
                return noteInfo as text
            end tell
            '''
        else:
            script = f'''
            tell application "Notes"
                set noteInfo to {{}}
                set counter to 0
                repeat with n in notes
                    if counter < {limit} then
                        set info to name of n & "|" & (creation date of n as string)
                        set end of noteInfo to info
                        set counter to counter + 1
                    end if
                end repeat
                return noteInfo as text
            end tell
            '''

        try:
            result = self._run_applescript_file(script)
            notes = []
            if result:
                for note_str in result.split(", "):
                    parts = note_str.split("|")
                    if len(parts) >= 1:
                        notes.append({
                            "title": parts[0],
                            "created": parts[1] if len(parts) > 1 else None
                        })
            return notes
        except OSAScriptError:
            return []

    def create_note(self, note: Note) -> bool:
        """
        Crea una nota.

        Args:
            note: Datos de la nota
        """
        # Escapar comillas en el body
        body_escaped = note.body.replace('"', '\\"').replace('\n', '\\n')

        script = f'''
        tell application "Notes"
            tell folder "{note.folder}"
                make new note with properties {{name:"{note.title}", body:"{body_escaped}"}}
            end tell
        end tell
        '''
        try:
            self._run_applescript_file(script)
            log.info(f"Note created: {note.title}")
            return True
        except OSAScriptError as e:
            log.error(f"Failed to create note: {e}")
            return False

    # =========================================================================
    # SAFARI
    # =========================================================================

    def get_safari_tabs(self) -> List[Dict]:
        """Obtiene las pestañas abiertas en Safari"""
        script = '''
        tell application "Safari"
            set tabInfo to {}
            repeat with w in windows
                repeat with t in tabs of w
                    set info to name of t & "|" & URL of t
                    set end of tabInfo to info
                end repeat
            end repeat
            return tabInfo as text
        end tell
        '''
        try:
            result = self._run_applescript_file(script)
            tabs = []
            if result:
                for tab_str in result.split(", "):
                    parts = tab_str.split("|")
                    if len(parts) >= 2:
                        tabs.append({
                            "title": parts[0],
                            "url": parts[1]
                        })
            return tabs
        except OSAScriptError:
            return []

    def get_current_safari_url(self) -> Optional[str]:
        """Obtiene la URL de la pestaña actual de Safari"""
        script = '''
        tell application "Safari"
            return URL of current tab of front window
        end tell
        '''
        try:
            return self._run_applescript_file(script)
        except OSAScriptError:
            return None

    def open_url_in_safari(self, url: str, new_tab: bool = True) -> bool:
        """
        Abre una URL en Safari.

        Args:
            url: URL a abrir
            new_tab: Abrir en nueva pestaña
        """
        if new_tab:
            script = f'''
            tell application "Safari"
                activate
                tell front window
                    set newTab to make new tab with properties {{URL:"{url}"}}
                    set current tab to newTab
                end tell
            end tell
            '''
        else:
            script = f'''
            tell application "Safari"
                activate
                set URL of current tab of front window to "{url}"
            end tell
            '''
        try:
            self._run_applescript_file(script)
            log.info(f"Opened URL in Safari: {url}")
            return True
        except OSAScriptError:
            return False

    # =========================================================================
    # CONTACTOS
    # =========================================================================

    def search_contacts(self, query: str) -> List[Dict]:
        """
        Busca contactos por nombre.

        Args:
            query: Texto a buscar
        """
        script = f'''
        tell application "Contacts"
            set matchingPeople to (every person whose name contains "{query}")
            set contactInfo to {{}}
            repeat with p in matchingPeople
                set info to name of p & "|" & (value of first email of p as string) & "|" & (value of first phone of p as string)
                set end of contactInfo to info
            end repeat
            return contactInfo as text
        end tell
        '''
        try:
            result = self._run_applescript_file(script)
            contacts = []
            if result:
                for contact_str in result.split(", "):
                    parts = contact_str.split("|")
                    if len(parts) >= 1:
                        contacts.append({
                            "name": parts[0],
                            "email": parts[1] if len(parts) > 1 and parts[1] != "missing value" else None,
                            "phone": parts[2] if len(parts) > 2 and parts[2] != "missing value" else None
                        })
            return contacts
        except OSAScriptError:
            return []

    # =========================================================================
    # FINDER
    # =========================================================================

    def get_selected_files(self) -> List[str]:
        """Obtiene los archivos seleccionados en Finder"""
        script = '''
        tell application "Finder"
            set selectedItems to selection
            set filePaths to {}
            repeat with item in selectedItems
                set end of filePaths to POSIX path of (item as alias)
            end repeat
            return filePaths as text
        end tell
        '''
        try:
            result = self._run_applescript_file(script)
            return [f.strip() for f in result.split(", ")] if result else []
        except OSAScriptError:
            return []

    def reveal_in_finder(self, path: str) -> bool:
        """Revela un archivo/carpeta en Finder"""
        script = f'''
        tell application "Finder"
            reveal POSIX file "{path}"
            activate
        end tell
        '''
        try:
            self._run_applescript_file(script)
            return True
        except OSAScriptError:
            return False

    # =========================================================================
    # CLIPBOARD
    # =========================================================================

    def get_clipboard(self) -> str:
        """Obtiene el contenido del portapapeles"""
        script = "the clipboard as text"
        try:
            return self._run_applescript(script)
        except OSAScriptError:
            return ""

    def set_clipboard(self, text: str) -> bool:
        """Establece el contenido del portapapeles"""
        script = f'set the clipboard to "{text}"'
        try:
            self._run_applescript(script)
            return True
        except OSAScriptError:
            return False

    # =========================================================================
    # MUSIC
    # =========================================================================

    def get_current_track(self) -> Optional[Dict]:
        """Obtiene la canción actual en Music"""
        script = '''
        tell application "Music"
            if player state is playing then
                set trackName to name of current track
                set artistName to artist of current track
                set albumName to album of current track
                return trackName & "|" & artistName & "|" & albumName
            else
                return ""
            end if
        end tell
        '''
        try:
            result = self._run_applescript_file(script)
            if result:
                parts = result.split("|")
                return {
                    "track": parts[0],
                    "artist": parts[1] if len(parts) > 1 else None,
                    "album": parts[2] if len(parts) > 2 else None
                }
            return None
        except OSAScriptError:
            return None

    def music_play_pause(self) -> bool:
        """Alterna reproducción en Music"""
        script = 'tell application "Music" to playpause'
        try:
            self._run_applescript(script)
            return True
        except OSAScriptError:
            return False


# Instancia global del servicio
osascript_service = OSAScriptService()
