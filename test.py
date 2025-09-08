import win32print

def list_printers():
    printers = []
    for printer in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS):
        printers.append(printer[2])
    return printers

printers = list_printers()
print("Available Printers:")
for printer in printers:
    print(f" - {printer}")