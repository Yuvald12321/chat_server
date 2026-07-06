call ".venv\Scripts\pyinstaller.exe" --onefile --noconsole --icon "logo.ico" --add-data "./templates/index.html;templates" -n "Local Chat Server" main.py
rd /S /Q "build"