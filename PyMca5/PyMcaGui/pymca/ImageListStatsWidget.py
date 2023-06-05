#/*##########################################################################
# Copyright (C) 2022-2023 European Synchrotron Radiation Facility
#
# This file is part of the PyMca X-ray Fluorescence Toolkit developed at
# the ESRF.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
#############################################################################*/
__author__ = "V.A. Sole - ESRF"
__contact__ = "sole@esrf.fr"
__license__ = "MIT"
__copyright__ = "European Synchrotron Radiation Facility, Grenoble, France"

import numpy

import logging
from PyMca5.PyMcaGui import PyMcaQt as qt
from PyMca5.PyMcaGui.misc import TableWidget
from PyMca5.PyMcaGui.misc import NumpyArrayTableModel
from PyMca5.PyMcaGraph import Colormap 
logger = logging.getLogger(__name__)

def arrayListPearsonCorrelation(imageList, mask=None):
    # the input imageList can be a 3D array or a list of images
    # the mask accounts for selected pixels
    # non-finite values are excluded
    if mask is not None:
        mask = mask.flatten()
    correlation = numpy.zeros((len(imageList), len(imageList)), dtype=numpy.float64)
    for i in range(len(imageList)):
        if mask is None:
            image0 = imageList[i].flatten()
        else:
            image0 = imageList[i].flatten()[mask > 0]
        for j in range(len(imageList)):
            if mask is None:
                image1 = imageList[j].flatten()
            else:
                image1 = imageList[j].flatten()[mask > 0]
            goodIndex = numpy.isfinite(image0) & numpy.isfinite(image1)
            image0 = image0[goodIndex]
            image1 = image1[goodIndex]
            image0_mean = image0.sum(dtype=numpy.float64) / image0.size
            image1_mean = image1.sum(dtype=numpy.float64) / image0.size
            image0 = image0 - image0_mean
            image1 = image1 - image1_mean
            cov = numpy.sum(image0 * image1) / image0.size
            stdImage0 = (numpy.sum(image0 * image0) /image0.size)**0.5
            stdImage1 = (numpy.sum(image1 * image1) /image1.size)**0.5
            correlation[i, j] = cov /(stdImage0 * stdImage1)
    return correlation

class ImageListStatsWidget(qt.QTabWidget):
    def __init__(self, parent=None):
        super(ImageListStatsWidget, self).__init__(parent=parent)
        self.tableWidget = TableWidget.TableWidget(parent=None, cut=False, paste=False)
        self.correlationWidget = TableWidget.TableView(parent=None, cut=False, paste=False)
        self.imageList = None
        self.imageMask = None
        labels = ["Name", "Maximum", "Minimum", "N", "Mean", "std"]
        self._stats = [x.lower() for x in labels]
        self.tableWidget.setColumnCount(len(self._stats))
        for i in range(len(labels)):
            item = self.tableWidget.horizontalHeaderItem(i)
            if item is None:
                item = qt.QTableWidgetItem(labels[i],
                                           qt.QTableWidgetItem.Type)
            item.setText(labels[i])
            self.tableWidget.setHorizontalHeaderItem(i,item)
        rheight = self.tableWidget.horizontalHeader().sizeHint().height()
        self.tableWidget.setMinimumHeight(5*rheight)
        self.addTab(self.tableWidget, "Stats")
        self.addTab(self.correlationWidget, "Correlation")

    def setImageList(self, images, image_names=None):
        if images is None:
            self.imageList = None
            self.imageMask = None
            self.updateStats()
            return
        if type(images) == type([]):
            self.imageList = images
            if image_names is None:
                self.imageNames = []
                for i in range(nimages):
                    self.imageNames.append("Image %02d" % i)
            else:
                self.imageNames = image_names
        elif len(images.shape) == 3:
            nimages = images.shape[0]
            self.imageList = [0] * nimages
            for i in range(nimages):
                self.imageList[i] = images[i,:]
                if 0:
                    #leave the data as they originally come
                    if self.imageList[i].max() < 0:
                        self.imageList[i] *= -1
                        if self.spectrumList is not None:
                            self.spectrumList [i] *= -1
            if image_names is None:
                self.imageNames = []
                for i in range(nimages):
                    self.imageNames.append("Image %02d" % i)
            else:
                self.imageNames = image_names

        newMask = None
        if self.imageList is not None:
            if len(self.imageList):
                if self.imageMask is not None:
                    if self.imageMask.shape == self.imageList[0].shape:
                        # we keep the mask
                        logger.info("Keeping previously defined mask")
                        newMask = self.imageMask

        self.imageMask = newMask
        self.updateStats()

    def setSelectionMask(self, mask=None):
        self.imageMask = mask
        self.updateStats()

    def updateStats(self):
        if self.imageList in [None, []]:
            self.tableWidget.setRowCount(0)
            return
        statsList = []
        mask = self.imageMask
        if mask is not None:
            mask = mask.flatten()
            if mask.min() == mask.max():
                if mask.min() == 0:
                    mask = None
        results = []
        for idx, imageName in enumerate(self.imageNames):
            result = {}
            image = self.imageList[idx].flatten()
            if mask is None:
                pass
            else:
                image = image[mask > 0]
            image = numpy.array(image[numpy.isfinite(image)], dtype=numpy.float64)
            result['name'] = imageName
            result['maximum'] = image.max()
            result['minimum'] = image.min()
            result['n'] = image.size
            result['mean'] = image.mean()
            result['std'] = image.std()
            results.append(result)

        # calculate pearson correlation
        correlation = arrayListPearsonCorrelation(self.imageList, mask)
        m = NumpyArrayTableModel.NumpyArrayTableModel(None, correlation, fmt = "%.5f")
        self.correlationWidget.setModel(m)
        bg = Colormap.applyColormap(correlation, colormap="temperature", norm="linear")
        m.setArrayColors(bg[0])
        m.setHorizontalHeaderLabels(self.imageNames)
        m.setVerticalHeaderLabels(self.imageNames)

        self._fillTable(results)

    def _fillTable(self, results):
        nRows = self.tableWidget.rowCount()
        nColumns = self.tableWidget.columnCount()
        self.tableWidget.setRowCount(len(results))
        for row, result in enumerate(results):
            for column, stat in enumerate(self._stats):
                if column == 0:
                    text = result[stat]
                else:
                    text = "%g" % result[stat]
                item = self.tableWidget.item(row, column)
                if item is None:
                    item = qt.QTableWidgetItem(text, qt.QTableWidgetItem.Type)
                    item.setTextAlignment(qt.Qt.AlignHCenter | qt.Qt.AlignVCenter)
                    item.setFlags(qt.Qt.ItemIsEnabled | qt.Qt.ItemIsSelectable)
                    self.tableWidget.setItem(row, column, item)
                else:
                    item.setText(text)

def main():
    w = ImageListStatsWidget()
    data = numpy.arange(20000)
    data.shape = 2, 100, 100
    data[1, 0:100,0:50] = 100
    w.setImageList(data, image_names=["I1", "I2"])
    w.show()
    return w

if __name__ == "__main__":
    app = qt.QApplication([])
    app.lastWindowClosed.connect(app.quit)
    w = main()
    app.exec()


