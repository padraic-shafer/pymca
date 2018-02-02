
import os
import sys
import traceback

from .SimpleFitGui import SimpleFitGui
from PyMca5.PyMcaGui import PyMcaQt as qt
from PyMca5.PyMcaCore import PyMcaDirs
from PyMca5.PyMcaMath.fitting import SimpleFitAll



class OutputParameters(qt.QWidget):
    def __init__(self, parent=None):
        qt.QWidget.__init__(self, parent)
        self.mainLayout = qt.QGridLayout(self)
        self.mainLayout.setContentsMargins(2, 2, 2, 2)
        self.mainLayout.setSpacing(2)
        self.outputDirLabel = qt.QLabel(self)
        self.outputDirLabel.setText("Output directory")
        self.outputDirLine = qt.QLineEdit(self)
        self.outputDirLine.setReadOnly(True)
        self.outputDirButton = qt.QPushButton(self)
        self.outputDirButton.setText("Browse")
        self.outputDirButton.clicked.connect(self.browseDirectory)

        self.outputFileLabel = qt.QLabel(self)
        self.outputFileLabel.setText("Output file root")
        self.outputFileLine = qt.QLineEdit(self)
        self.outputFileLine.setReadOnly(True)

        self.outputDir = PyMcaDirs.outputDir
        self.outputFile = "SimpleFitAllOutput.h5"
        self.setOutputDirectory(self.outputDir)
        self.setOutputFileBaseName(self.outputFile)

        self.mainLayout.addWidget(self.outputDirLabel, 0, 0)
        self.mainLayout.addWidget(self.outputDirLine, 0, 1)
        self.mainLayout.addWidget(self.outputDirButton, 0, 2)
        self.mainLayout.addWidget(self.outputFileLabel, 1, 0)
        self.mainLayout.addWidget(self.outputFileLine, 1, 1)

    def getOutputDirectory(self):
        return qt.safe_str(self.outputDirLine.text())

    def getOutputFileName(self):
        return qt.safe_str(self.outputFileLine.text())

    def setOutputDirectory(self, txt):
        if os.path.exists(txt):
            self.outputDirLine.setText(txt)
            self.outputDir = txt
            PyMcaDirs.outputDir = txt
        else:
            raise IOError("Directory does not exists")

    def setOutputFileBaseName(self, txt):
        if len(txt):
            self.outputFileLine.setText(txt)
            self.outputFile = txt

    def browseDirectory(self):
        wdir = self.outputDir
        outputDir = qt.QFileDialog.getExistingDirectory(self,
                                                        "Please select output directory",
                                                        wdir)
        if len(outputDir):
            self.setOutputDirectory(qt.safe_str(outputDir))


class SimpleFitAllGui(SimpleFitGui):

    def __init__(self, parent=None, fit=None, graph=None, actions=True):
        SimpleFitGui.__init__(self, parent, fit, graph, actions)

        self.fitAllInstance = SimpleFitAll.SimpleFitAll(fit=self.fitModule)

        self.fitActions.dismissButton.hide()
        self.outputParameters = OutputParameters(self)
        self.startButton = qt.QPushButton(self)
        self.startButton.setText("Fit all")
        self.startButton.clicked.connect(self.startFitAll)
        self.progressBar = qt.QProgressBar(self)
        self.mainLayout.addWidget(self.outputParameters)
        self.mainLayout.addWidget(self.startButton)
        self.mainLayout.addWidget(self.progressBar)

        # progress handling
        self._total = 100
        self._index = 0
        self.fitAllInstance.setProgressCallback(self.progressBarUpdate)

    def setCurves(self, x, curves_y, data_index=-1):
        """Set data to be fitted"""
        self.curves_x = x
        self.curves_y = curves_y

        if data_index < 0:
            data_index += len(curves_y.shape)
        self.data_index = data_index

    def startFitAll(self):
        xmin = self.fitModule._fitConfiguration['fit']['xmin']
        xmax = self.fitModule._fitConfiguration['fit']['xmax']
        self.fitAllInstance.setOutputDirectory(
                self.outputParameters.getOutputDirectory())
        self.fitAllInstance.setOutputFileName(
                self.outputParameters.getOutputFileName())
        self.fitAllInstance.setData(self.curves_x, self.curves_y,
                                    sigma=None, xmin=xmin, xmax=xmax)

        self.fitAllInstance.setDataIndex(self.data_index)

        fileName = self.outputParameters.getOutputFileName()
        deleteFile = False
        if os.path.exists(fileName):
            msg = qt.QMessageBox()
            msg.setWindowTitle("Output file(s) exists")
            msg.setIcon(qt.QMessageBox.Information)
            msg.setText("Do you want to delete current output files?")
            msg.setStandardButtons(qt.QMessageBox.Yes | qt.QMessageBox.No)
            answer = msg.exec_()
            if answer == qt.QMessageBox.Yes:
                try:
                    if os.path.exists(fileName):
                        os.remove(fileName)
                except:
                    qt.QMessageBox.critical(
                        self, "Delete Error",
                        "ERROR while deleting file:\n%s" % fileName,
                        qt.QMessageBox.Ok,
                        qt.QMessageBox.NoButton,
                        qt.QMessageBox.NoButton)
                    return
        try:
            self._startWork()
        except:
            msg = qt.QMessageBox(self)
            msg.setIcon(qt.QMessageBox.Critical)
            msg.setWindowTitle("Fitting All Error")
            msg.setText("Error has occurred while processing the data")
            msg.setInformativeText(qt.safe_str(sys.exc_info()[1]))
            msg.setDetailedText(traceback.format_exc())
            msg.exec_()
        finally:
            self.progressBar.hide()
            self.setEnabled(True)

    def _startWork(self):


