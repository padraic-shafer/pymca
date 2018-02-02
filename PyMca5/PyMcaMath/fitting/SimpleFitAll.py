#/*##########################################################################
#
# The PyMca X-Ray Fluorescence Toolkit
#
# Copyright (c) 2004-2017 European Synchrotron Radiation Facility
#
# This file is part of the PyMca X-ray Fluorescence Toolkit developed at
# the ESRF by the Software group.
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
import sys
import os
import numpy
from PyMca5.PyMcaIO import ConfigDict
from PyMca5.PyMcaIO import ArraySave
from PyMca5 import PyMcaDirs


class SimpleFitAll(object):
    def __init__(self, fit):
        self.fit = fit
        self.curves_y = None
        self.outputDir = PyMcaDirs.outputDir
        self.outputFile = None
        self.fixedLenghtOutput = True
        self._progress = 0.0
        self._status = "Ready"
        self.progressCallback = None
        self.dataIndex = None
        # optimization variables
        self.mask = None
        self.__ALWAYS_ESTIMATE = True

    def setProgressCallback(self, method):
        """
        The method will be called as method(current_fit_index, total_fit_index)
        """
        self.progressCallback = method

    def progressUpdate(self):
        """
        This method returns a dictionnary with the keys
        progress: A number between 0 and 100 indicating the fit progress
        status: Status of the calculation thread.
        """
        ddict = {
            'progress': self._progress,
            'status': self._status}
        return ddict

    def setOutputDirectory(self, outputdir):
        self.outputDir = outputdir

    def setOutputFileName(self, outputfile):
        self.outputFile = outputfile

    def setData(self, curves_x, curves_y, sigma=None, xmin=None, xmax=None):
        self.curves_x = curves_x
        self.curves_y = curves_y
        self.curves_sigma = sigma
        self.xMin = xmin
        self.xMax = xmax

    def setDataIndex(self, data_index=None):
        self.dataIndex = data_index

    # TODO
    def setConfigurationFile(self, fname):
        if not os.path.exists(fname):
            raise IOError("File %s does not exist" % fname)
        w = ConfigDict.ConfigDict()
        w.read(fname)
        self.setConfiguration(w)

    def setConfiguration(self, ddict):
        self.fit.setConfiguration(ddict, try_import=True)

    def processAll(self, mask=None):
        self.mask = mask
        data_index = self.dataIndex
        if data_index == None:
            data_index = -1
        if type(data_index) == type(1):
            data_index = [data_index]

        if len(data_index) > 1:
            raise IndexError("Only 1D fitting implemented for the time being")

        #this leaves the possibility to fit images by giving
        #two indices specifying the image dimensions
        self.stackDataIndexList = data_index

        stack = self.curves_y
        if stack is None:
            raise ValueError("No data to be processed")

        if hasattr(stack, "info") and hasattr(stack, "data"):
            data = stack.data
        else:
            data = stack

        #make sure all the indices are positive
        for i in range(len(data_index)):
            if data_index[i] < 0:
                data_index[i] = range(len(data.shape))[data_index[i]]

        #get the total number of fits to be performed
        outputDimension = []
        nPixels = 1
        for i in range(len(data.shape)):
            if not (i in data_index):
                nPixels *= data.shape[i]
                outputDimension.append(data.shape[i])

        lenOutput = len(outputDimension)
        if lenOutput > 2:
            raise ValueError("Rank of  output greater than 2")
        elif lenOutput == 2:
            self._nRows = outputDimension[0]
            self._nColumns = outputDimension[1]
        else:
            self._nRows = outputDimension[0]
            self._nColumns = 1

        if self.mask is not None:
            if (self.mask.shape[0] != self._nRows) or\
               (self.mask.shape[1] != self._nColumns):
                raise ValueError("Invalid mask shape for stack")
        else:
            self.mask = numpy.ones((self._nRows, self._nColumns),
                                   numpy.uint8)

        # optimization
        self.__ALWAYS_ESTIMATE = True
        backgroundPolicy = self.fit._fitConfiguration['fit'] \
                           ['background_estimation_policy']
        functionPolicy = self.fit._fitConfiguration['fit'] \
                         ['function_estimation_policy']
        if "Estimate always" not in [functionPolicy, backgroundPolicy]:
            self.__ALWAYS_ESTIMATE = False

        # initialize control variables
        self._parameters = None
        self._row = 0
        self._column = -1
        self._progress = 0
        self._status = "Fitting"
        for i in range(nPixels):
            self._progress = (i * 100.)/ nPixels
            if (self._column+1) == self._nColumns:
                self._column = 0
                self._row   += 1
            else:
                self._column += 1
            try:
                if self.mask[self._row, self._column]:
                    self.processStackData(i)
            except:
                print("Error %s processing index = %d, row = %d column = %d" %\
                        (sys.exc_info()[1], i, self._row, self._column))
                if DEBUG:
                    raise
        self.onProcessStackFinished()
        self._status = "Ready"
        if self.progressCallback is not None:
            self.progressCallback(nPixels, nPixels)

    def processStackData(self, i):
        self.aboutToGetStackData(i)
        x, y, sigma, xmin, xmax = self.getFitInputValues(i)
        self.fit.setData(x, y, sigma=sigma, xmin=xmin, xmax=xmax)
        if self._parameters is None:
            if DEBUG:
                print("First estimation")
            self.fit.estimate()
        elif self.__ALWAYS_ESTIMATE:
            if DEBUG:
                print("Estimation due to settings")
            self.fit.estimate()
        self.estimateFinished()
        values, chisq, sigma, niter, lastdeltachi = self.fit.startFit()
        self.fitFinished()

    def getFitInputValues(self, index):
        """
        Returns the fit parameters x, y, sigma, xmin, xmax
        """
        row    = self._row
        column = self._column
        data_index = self.stackDataIndexList[0]

        #get y
        yShape = self.curves_y.shape
        if len(yShape) == 3:
            if data_index == 0:
                y = self.curves_y[:, row, column]
            elif data_index == 1:
                y = self.curves_y[row, :, column]
            else:
                y = self.curves_y[row, column]
        elif len(yShape) == 2:
            if column > 0:
                raise ValueError("Column index > 0 on a single column stack")
            y = self.curves_y[row]
        else:
            raise TypeError("Unsupported y data shape lenght")

        #get x
        if self.curves_x is None:
            nValues = y.size
            x = numpy.arange(float(nValues))
            x.shape = y.shape
            self.curves_x = x

        xShape = self.curves_x.shape
        xSize  = self.curves_x.size
        sigma = None
        if xShape == yShape:
            #as many x as y, follow same criterium
            if len(xShape) == 3:
                if data_index == 0:
                    x = self.curves_x[:, row, column]
                elif data_index == 1:
                    x = self.curves_x[row, :, column]
                else:
                    x = self.curves_x[row, column]
            elif len(xShape) == 2:
                if column > 0:
                    raise ValueError("Column index > 0 on a single column stack")
                x = self.curves_x[row]
            else:
                raise TypeError("Unsupported x data shape lenght")
        elif xSize == y.size:
            #only one x for all the y values
            x = numpy.zeros(y.size, numpy.float)
            x[:] = self.curves_x[:]
            x.shape = y.shape
        else:
            raise ValueError("Cannot handle incompatible X and Y values")

        if self.curves_sigma is None:
            return x, y, sigma, self.xMin, self.xMax

        # get sigma
        sigmaShape = self.curves_sigma.shape
        sigmaSize  = self.curves_sigma.size

        if sigmaShape == yShape:
            #as many sigma as y, follow same criterium
            if len(sigmaShape) == 3:
                if data_index == 0:
                    sigma = self.curves_sigma[:, row, column]
                elif data_index == 1:
                    sigma = self.curves_sigma[row, :, column]
                else:
                    sigma = self.curves_sigma[row, column]
            elif len(sigmaShape) == 2:
                if column > 0:
                    raise ValueError("Column index > 0 on a single column stack")
                sigma = self.curves_sigma[row]
            else:
                raise TypeError("Unsupported sigma data shape lenght")
        elif sigmaSize == y.size:
            #only one sigma for all the y values
            sigma = numpy.zeros(y.size, numpy.float)
            sgima[:] = self.curves_sigma[:]
            sigma.shape = y.shape
        else:
            raise ValueError("Cannot handle incompatible sigma and y values")

        return x, y, sigma, self.xMin, self.xMax

    def estimateFinished(self):
        if DEBUG:
            print("Estimate finished")

    def aboutToGetStackData(self, idx):
        if DEBUG:
            print("New spectrum %d" % idx)
        self._currentFitIndex = idx
        if self.progressCallback is not None:
            self.progressCallback(idx, self._nRows * self._nColumns)

        if idx == 0:
            specfile = os.path.join(self.outputDir,
                                    self.outputFile+".spec")
            if os.path.exists(self.outputFile):
                os.remove(self.outputFile)

    def fitFinished(self):
        if DEBUG:
            print("fit finished")

        #get parameter results
        fitOutput = self.fit.getResult(configuration=False)
        result = fitOutput['result']
        row= self._row
        column = self._column
        if result is None:
            print("result not valid for row %d, column %d" % (row, column))
            return

        if self.fixedLenghtOutput and (self._parameters is None):
            #If it is the first fit, initialize results array
            imgdir = os.path.join(self.outputDir, "IMAGES")
            if not os.path.exists(imgdir):
                os.mkdir(imgdir)
            if not os.path.isdir(imgdir):
                msg= "%s does not seem to be a valid directory" % imgdir
                raise IOError(msg)
            self.imgDir = imgdir
            self._parameters  = []
            self._images      = {}
            self._sigmas      = {}
            for parameter in result['parameters']:
                self._parameters.append(parameter)
                self._images[parameter] = numpy.zeros((self._nRows,
                                                       self._nColumns),
                                                       numpy.float32)
                self._sigmas[parameter] = numpy.zeros((self._nRows,
                                                       self._nColumns),
                                                       numpy.float32)
            self._images['chisq'] = numpy.zeros((self._nRows,
                                                       self._nColumns),
                                                       numpy.float32)

        if self.fixedLenghtOutput:
            i = 0
            for parameter in self._parameters:
                self._images[parameter] [row, column] =\
                                        result['fittedvalues'][i]
                self._sigmas[parameter] [row, column] =\
                                        result['sigma_values'][i]
                i += 1
            self._images['chisq'][row, column] = result['chisq']
        else:
            #specfile output always available
            specfile = self.getOutputFileNames()['specfile']
            self._appendOneResultToSpecfile(specfile, result=fitOutput)

    def _appendOneResultToSpecfile(self, filename, result=None):
        if result is None:
            result = self.fit.getResult(configuration=False)

        scanNumber = self._currentFitIndex

        #open file in append mode
        fitResult = result['result']
        fittedValues = fitResult['fittedvalues']
        fittedParameters = fitResult['parameters']
        chisq = fitResult['chisq']
        text = "\n#S %d %s\n" % (scanNumber, "PyMca Stack Simple Fit")
        text += "#N %d\n" % (len(fittedParameters)+2)
        text += "#L N  Chisq"
        for parName in fittedParameters:
            text += '  %s' % parName
        text += "\n"
        text += "1 %f" % chisq
        for parValue in fittedValues:
            text += "% .7E" % parValue
        text += "\n"
        sf = open(filename, 'ab')
        sf.write(text)
        sf.close()

    def getOutputFileNames(self):
        specfile = os.path.join(self.outputDir,
                                self.outputFile+".spec")
        imgDir = os.path.join(self.outputDir, "IMAGES")
        filename = os.path.join(imgDir, self.outputFile)
        csv = filename + ".csv"
        edf = filename + ".edf"
        ddict = {}
        ddict['specfile'] = specfile
        ddict['csv'] = csv
        ddict['edf'] = edf
        return ddict

    def onProcessStackFinished(self):
        if DEBUG:
            print("Stack proccessed")
        self._status = "Stack Fitting finished"
        if self.fixedLenghtOutput:
            self._status = "Writing output files"
            nParameters = len(self._parameters)
            datalist = [None] * (2*len(self._sigmas.keys())+1)
            labels = []
            for i in range(nParameters):
                parameter = self._parameters[i]
                datalist[2*i] = self._images[parameter]
                datalist[2*i + 1] = self._sigmas[parameter]
                labels.append(parameter)
                labels.append('s(%s)' % parameter)
            datalist[-1] = self._images['chisq']
            labels.append('chisq')
            filenames = self.getOutputFileNames()
            csvName = filenames['csv']
            edfName = filenames['edf']
            ArraySave.save2DArrayListAsASCII(datalist,
                                             csvName,
                                             labels=labels,
                                             csv=True,
                                             csvseparator=";")
            ArraySave.save2DArrayListAsEDF(datalist,
                                           edfName,
                                           labels = labels,
                                           dtype=numpy.float32)

def test():
    import numpy
    from PyMca5.PyMcaMath.fitting import SpecfitFuns
    x = numpy.arange(1000.)
    data = numpy.zeros((50, 1000), numpy.float)

    #the peaks to be fitted
    p0 = [100., 300., 50.,
          200., 500., 30.,
          300., 800., 65]

    #generate the data to be fitted
    for i in range(data.shape[0]):
        nPeaks = 3 - i % 3
        data[i,:] = SpecfitFuns.gauss(p0[:3*nPeaks],x)

    oldShape = data.shape
    data.shape = 1,oldShape[0], oldShape[1]

    instance = StackSimpleFit()
    instance.setData(x, data)
    # TODO: Generate this file "on-the-fly" to be able to test everywhere
    instance.setConfigurationFile("C:\StackSimpleFit.cfg")
    instance.processAll()

if __name__=="__main__":
    DEBUG = 0
    test()
