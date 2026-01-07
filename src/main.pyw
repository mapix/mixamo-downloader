# Third-party modules
from PySide2 import QtWidgets, QtCore
import sys
import signal
import os

# Local modules
from ui import MixamoDownloaderUI


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\n\nReceived interrupt signal, forcing exit...")
    # Force exit immediately without cleanup to avoid hanging
    os._exit(0)


if __name__ == "__main__":
    # Install signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    # Set application properties
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_ShareOpenGLContexts)
    
    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    
    # Create main window
    md = MixamoDownloaderUI()
    md.show()
    
    # Setup a timer to handle Ctrl+C in Qt event loop
    timer = QtCore.QTimer()
    timer.timeout.connect(lambda: None)  # Allow Python to handle signals
    timer.start(100)
    
    # Run application
    try:
        exit_code = app.exec_()
    except KeyboardInterrupt:
        print("\n\nKeyboard interrupt, exiting...")
        exit_code = 0
    
    # Quick cleanup - don't wait for slow operations
    try:
        if hasattr(md, 'browser') and md.browser:
            md.browser.deleteLater()
    except:
        pass
    
    # Force exit to avoid hanging on WebEngine cleanup
    os._exit(exit_code)
