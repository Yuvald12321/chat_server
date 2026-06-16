pyinstaller --noconsole --onefile --icon logo.ico --add-data "templates/index.html;templates" -n "Local Chat Server" main.py
rd /S /Q "build"
del /Q "Local Chat Server.spec"
