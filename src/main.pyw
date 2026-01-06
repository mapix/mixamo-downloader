# Third-party modules
from PySide2 import QtWidgets, QtCore
import sys

# Local modules
from ui import MixamoDownloaderUI


if __name__ == "__main__":
    # 设置应用程序属性
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_ShareOpenGLContexts)
    
    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    
    # 创建主窗口
    md = MixamoDownloaderUI()
    md.show()
    
    # 运行应用
    exit_code = app.exec_()
    
    # 确保所有资源被清理
    del md
    del app
    
    # 退出
    sys.exit(exit_code)
