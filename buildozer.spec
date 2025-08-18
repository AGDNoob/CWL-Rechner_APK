[app]
title = CWL Bonus Rechner
package.name = cwlrechner
package.domain = org.clan.cwlrechner
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
version = 1.0
requirements = python3,kivy,pandas,plyer,xlsxwriter,openpyxl
orientation = portrait
permissions = WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE
fullscreen = 0

[buildozer]
log_level = 2
warn_on_root = 1