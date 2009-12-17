#
#   Authors: Megan Sosey, Christopher Hanley
#   Program: stisData.py
#   Purpose: Class used to import STIS specific instrument data.

from pytools import fileutil
import numpy as np
from imagemanip import interp2d
from imageObject import imageObject
from staticMask import constructFilename


class STISInputImage (imageObject):

    SEPARATOR = '_'

    def __init__(self,filename=None,group=None):
        imageObject.__init__(self,filename,group=group)
       
        # define the cosmic ray bits value to use in the dq array
        self.cr_bits_value = 8192
        self._effGain = 1.
        self._instrument=self._image["PRIMARY"].header["INSTRUME"] #this just shows instrument, not detector, detector asigned by subclass
        
                
    def getflat(self):
        """

        Purpose
        =======
        Method for retrieving a detector's flat field.  For STIS there are three 
        
        
        This method will return an array the same shape as the
        image.
        
        """

        # The keyword for STIS flat fields in the primary header of the flt
        
        lflatfile = self._image["PRIMARY"].header['LFLTFILE']
        pflatfile = self._image["PRIMARY"].header['PFLTFILE']
        
        # Try to open the file in the location specified by LFLTFILE.
        try:
            handle = fileutil.openImage(lflatfile,mode='readonly',memmap=0)
            hdu = fileutil.getExtn(handle,extn=self.extn)
            lfltdata = hdu.data
            if lfltdata.shape != self.full_shape:
                lfltdata = interp2d.expand2d(lfltdata,self.full_shape)
        except:
            # If the user forgot to specifiy oref try looking for the reference
            # file in the current directory
            try:
                handle = fileutil.openImage(lfltfile[5:],mode='readonly',memmap=0)
                hdu = fileutil.getExtn(handle,extn=self.extn)
                lfltdata = hdu.data
            # No flat field was found.  Assume the flat field is a constant value of 1.
            except:
                lfltdata = np.ones(self.full_shape,dtype=self.image_dtype)
                str = "Cannot find file "+filename+".  Treating flatfield constant value of '1'.\n"
                print str
        
        # Try to open the file in the location specified by PFLTFILE.
        try:
            handle = fileutil.openImage(pflatfile,mode='readonly',memmap=0)
            hdu = fileutil.getExtn(handle,extn=self.extn)
            pfltdata = hdu.data
        except:
            # If the user forgot to specifiy oref try looking for the reference
            # file in the current directory
            try:
                handle = fileutil.openImage(pfltfile[5:],mode='readonly',memmap=0)
                hdu = fileutil.getExtn(handle,extn=self.extn)
                pfltdata = hdu.data
            # No flat field was found.  Assume the flat field is a constant value of 1.
            except:
                pfltdata = np.ones(self.image_shape,dtype=self.image_dtype)
                str = "Cannot find file "+filename+".  Treating flatfield constant value of '1'.\n"
                print str
        
        print "lfltdata shape: ",lfltdata.shape
        print "pfltdata shape: ",pfltdata.shape
        flat = lfltdata * pfltdata
        
        return flat

    def doUnitConversions(self):
        """convert the data to electrons
        
        This converts all science data extensions and saves
        the results back to disk. We need to make sure
        the data inside the chips already in memory is altered as well
        
        """
        

         # Image information 
        _handle = fileutil.openImage(self._filename,mode='update',memmap=0) 

        for det in range(1,self._numchips+1,1):

            chip=self._image[self.scienceExt,det]
            
            if chip._gain != None:

                # Multiply the values of the sci extension pixels by the gain. 
                print "Converting %s[%s,%d] from COUNTS to ELECTRONS"%(self._filename,self.scienceExt,det) 

                # If the exptime is 0 the science image will be zeroed out. 
                np.multiply(_handle[self.scienceExt,det].data,chip._gain,_handle[self.scienceExt,det].data)
                chip.data=_handle[det].data

                # Set the BUNIT keyword to 'electrons'
                _handle[det].header.update('BUNIT','ELECTRONS')

                # Update the PHOTFLAM value
                photflam = _handle[det].header['PHOTFLAM']
                _handle[det].header.update('PHOTFLAM',(photflam/self._gain()))
                
                chip._effGain = 1.
            
            else:
                print "Invalid gain value for data, no conversion done"
                return ValueError

        # Close the files and clean-up
        _handle.close() 

        self._effGain = 1.

    def _assignSignature(self, chip):
        """assign a unique signature for the image based 
           on the  instrument, detector, chip, and size
           this will be used to uniquely identify the appropriate
           static mask for the image
           
           this also records the filename for the static mask to the outputNames dictionary
           
        """
        sci_chip = self._image[self.scienceExt,chip]
        ny=sci_chip._naxis1
        nx=sci_chip._naxis2
        detnum = sci_chip.detnum
        instr=self._instrument
        
        sig=(instr+self._detector,(nx,ny),int(detnum)) #signature is a tuple
        sci_chip.signature=sig #signature is a tuple
        filename=constructFilename(sig)
        sci_chip.outputNames["staticMask"]=filename #this is the name of the static mask file



class CCDInputImage(STISInputImage):

    def __init__(self,filename=None,group=None):
        STISInputImage.__init__(self,filename,group=group)

        self.full_shape = (1024,1024)
        self._detector=self._image["PRIMARY"].header["DETECTOR"]  
        
        
        #if ( self.amp == 'D' or self.amp == 'C' ) : # cte direction depends on amp 
        self.cte_dir =  1 
        #if ( self.amp == 'A' or self.amp == 'B' ) :
        #    self.cte_dir =  -1  

    def getdarkcurrent(self):
        darkcurrent = 0.009 #electrons/sec
        if self.proc_unit == 'native':
            return darkcurrent / self._gain()
        return darkcurrent
    
    def getReadNoise(self):
        """
        
        Purpose
        =======
        Method for trturning the readnoise of a detector (in DN).
        
        :units: DN
        
        this should work on a chip, since different chips to be consistant with other 
        detector classes where different chips have different gains
        
        """
        if self.proc_unit == 'native':
            return self._rdnoise / self._gain()
        return self._rdnoise
    
    def setInstrumentParameters(self, instrpars):
        """ This method overrides the superclass to set default values into
            the parameter dictionary, in case empty entries are provided.
        """
        #pri_header = self._image[0].header

        if self._isNotValid (instrpars['gain'], instrpars['gnkeyword']):
            instrpars['gnkeyword'] = 'ATODGAIN'
        if self._isNotValid (instrpars['rdnoise'], instrpars['rnkeyword']):
            instrpars['rnkeyword'] = 'READNSE'
        if self._isNotValid (instrpars['exptime'], instrpars['expkeyword']):
            instrpars['expkeyword'] = 'EXPTIME'

        for chip in self.returnAllChips(extname=self.scienceExt):
            pri_header=chip.header
            
            chip._gain      = self.getInstrParameter(instrpars['gain'], pri_header,
                                                     instrpars['gnkeyword'])
            chip._rdnoise   = self.getInstrParameter(instrpars['rdnoise'], pri_header,
                                                     instrpars['rnkeyword'])
            chip._exptime   = self.getInstrParameter(instrpars['exptime'], pri_header,
                                                     instrpars['expkeyword'])

            if chip._gain == None or chip._rdnoise == None or chip._exptime == None:
                print 'ERROR: invalid instrument task parameter'
                raise ValueError
            
            chip._effGain = chip._gain
            
            self._assignSignature(chip._chip) #this is used in the static mask                     


        self.doUnitConversions()

    
class NUVInputImage(STISInputImage):
    def __init__(self, input, dqname, platescale, memmap=0,proc_unit="native"):
        STISInputImage.__init__(self,input,dqname,platescale,memmap=0,proc_unit=proc_unit)

        self._detector=self._image["PRIMARY"].header["DETECTOR"]  
        
        # no cte correction for STIS/NUV-MAMA so set cte_dir=0.
        print('\nWARNING: No cte correction will be made for this STIS/NUV-MAMA data.\n')
        self.cte_dir = 0  

    def setInstrumentParameters(self, instrpars):
        """ This method overrides the superclass to set default values into
            the parameter dictionary, in case empty entries are provided.
        """

        pri_header = self._image[0].header

        if self._isNotValid (instrpars['gain'], instrpars['gnkeyword']):
            instrpars['gnkeyword'] = None
        if self._isNotValid (instrpars['rdnoise'], instrpars['rnkeyword']):
            instrpars['rnkeyword'] = None
        if self._isNotValid (instrpars['exptime'], instrpars['expkeyword']):
            instrpars['expkeyword'] = 'EXPTIME'

       # We need to determine if the user has used the default readnoise/gain value
        # since if not, they will need to supply a gain/readnoise value as well                
        usingDefaultGain = False
        usingDefaultReadnoise = False
        if (instrpars['gnkeyword'] == None):
            usingDefaultGain = True
        if (instrpars['rnkeyword'] == None):
            usingDefaultReadnoise = True


        for chip in self.returnAllChips(extname=self.scienceExt):
            pri_header=chip.header
            chip.cte_dir=0
            # We need to treat Read Noise and Gain as a special case since it is 
            # not populated in the STIS primary header for the MAMAs
            if (instrpars['rnkeyword'] != None):
                chip._rdnoise   = self.getInstrParameter(instrpars['rdnoise'], pri_header,
                                                         instrpars['rnkeyword'])                                                 
            else:
                chip._rdnoise = None

            if (instrpars['gnkeyword'] != None):
                chip._gain = self.getInstrParameter(instrpars['gain'], pri_header,
                                                         instrpars['gnkeyword'])
            else:
                chip._gain = None

            # Set the default readnoise or gain values based upon the amount of user input given.

            if usingDefaultReadnoise:
                chip._rdnoise= self._setMAMADefaultReadnoise()

            if usingDefaultGain:
                chip._gain = self._setMAMADefaultGain()
          
            self._assignSignature(chip._chip) #this is used in the static mask                     
            


            chip._exptime   = self.getInstrParameter(instrpars['exptime'], pri_header,
                                                     instrpars['expkeyword'])

            if chip._exptime == None:
                print 'ERROR: invalid instrument task parameter'
                raise ValueError
        # Convert the science data to electrons if specified by the user.  
        self.doUnitConversions()

   

    def _setMAMAchippars(self):
        self._setMAMADefaultGain()
        self._setMAMADefaultReadnoise()
     
    def _setMAMADefaultGain(self):
        self._gain = 1

    def _setMAMADefaultReadnoise(self):
        self._rdnoise = 0


 
    def getdarkcurrent(self):
        darkcurrent = 0.0013 #electrons/sec
        if self.proc_unit == 'native':
            return darkcurrent / self._gain()
        return darkcurrent
    
class FUVInputImage(STISInputImage):
    def __init__(self,filename=None,group=None):
        STISInputImage.__init__(self,filename,group=group)
        self._detector=self._image["PRIMARY"].header["DETECTOR"] 
        
        # no cte correction for STIS/FUV-MAMA so set cte_dir=0.
        print('\nWARNING: No cte correction will be made for this STIS/FUV-MAMA data.\n')
        self.cte_dir = 0  
        self.effGain=1.0

    def setInstrumentParameters(self, instrpars):
        """ This method overrides the superclass to set default values into
            the parameter dictionary, in case empty entries are provided.
        """
        
        pri_header = self._image[0].header   
        usingDefaultGain = False
        usingDefaultReadnoise = False
              
        if self._isNotValid (instrpars['gain'], instrpars['gnkeyword']):
            instrpars['gnkeyword'] = None
        if self._isNotValid (instrpars['rdnoise'], instrpars['rnkeyword']):
            instrpars['rnkeyword'] = None
        if self._isNotValid (instrpars['exptime'], instrpars['expkeyword']):
            instrpars['expkeyword'] = 'EXPTIME'
            
        for chip in self.returnAllChips(extname=self.scienceExt): 
            pri_header=chip.header #stis stores stuff in the science data header
        
            chip.cte_dir=0

            chip._exptime   = self.getInstrParameter(instrpars['exptime'], pri_header,
                                                     instrpars['expkeyword'])
            if chip._exptime == None:
                print 'ERROR: invalid instrument task parameter'
                raise ValueError

            if (instrpars['rnkeyword'] != None):
                chip._rdnoise   = self.getInstrParameter(instrpars['rdnoise'], pri_header,
                                                         instrpars['rnkeyword'])                                                 
            else:
                chip._rdnoise = None
                usingDefaultReadnoise = True
                
            if (instrpars['gnkeyword'] != None):
                chip._gain = self.getInstrParameter(instrpars['gain'], pri_header,
                                                         instrpars['gnkeyword'])
            else:
                chip._gain = None
                usingDefaultGain = True

            if chip._exptime == None:
                print 'ERROR: invalid instrument task parameter'
                raise ValueError

            # We need to determine if the user has used the default readnoise/gain value
            # since if not, they will need to supply a gain/readnoise value as well                

            if usingDefaultReadnoise:
                chip._rdnoise= self._setMAMADefaultReadnoise()

            if usingDefaultGain:
                chip._gain = self._setMAMADefaultGain()
          
            self._assignSignature(chip._chip) #this is used in the static mask                     
            chip._effGain=chip._gain

        # Convert the science data to electrons if specified by the user.  
        self.doUnitConversions()

              
    def getdarkcurrent(self):
        darkcurrent = 0.07 #electrons/sec
        if self.proc_unit == 'native':
            return darkcurrent / self._gain()
        return darkcurrent

    
    def _setMAMADefaultGain(self):
        return 1

    def _setMAMADefaultReadnoise(self):
        return 0
