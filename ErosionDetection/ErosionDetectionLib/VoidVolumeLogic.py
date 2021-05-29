#-----------------------------------------------------
# VoidVolumeLogic.py
#
# Created by:  Mingjie Zhao
# Created on:  16-10-2020
#
# Description: This module identifies cortical interruptions and 
#              erosions on the input image. 
#              First, the input image is binarized with a global threshold. 
#              Next, a distance transformation and morphological opening operations
#              (i.e. erode, connectivity, dilate) are applied 
#              to select the large void volumes. 
#              Then, the above steps are repeated with more 'aggressive' parameters. 
#              Lastly, the two void volumes obtained are combined to yield the final output. 
#              There are 8 steps.
#
#-----------------------------------------------------
# Usage:       This module is plugged into 3D Slicer, but can run on its own. 
#              When running on its own, call:
#              python VoidVolume.py inputImage inputMask outputImage seeds
#                                   lowerThreshold upperThreshold
#                                   [minimalRadius] [morphologicalRadius]
#
# Param:       inputImage: The input scan file path
#              inputMask: The input mask file path
#              outputImage: The output image file path
#              seeds: The seed points csv file path
#              lowerThreshold
#              upperThreshold
#              minimalRadius: Minimal erosion radius in voxels, default=3
#              morphologicalRadius: Morphological kernel radius in voxels, default=5
#
#-----------------------------------------------------
import SimpleITK as sitk

class VoidVolumeLogic:
    def __init__(self, img=None, mask=None, lower=3000, upper=10000, seeds=None,
    minimalRadius=3, morphologicalRadius=5):
        self.model_img = img                  # greyscale scan
        self.contour_img = None               # mask, periosteal boundary
        if ((self.model_img is not None) and (mask is not None)):
            self.setContourImage(mask)
        self.ero1_img = None                  # erosions with less trabecular leakage
        self.ero2_img = None                  # erosions with more trabecular leakage
        self.output_img = None
        self.lower_threshold = lower
        self.upper_threshold = upper
        self.minimalRadius = minimalRadius               # for distance transformation
        self.morphologicalRadius = morphologicalRadius   # for morphological operations
        self.seeds = seeds         # list of seed point coordinates (x,y,z)
        self.stepNum = 8           # number of steps in the algorithm
        self._step = 0             # number of steps done
    
    def smoothen(self, img, lower, upper):
        """
        Binarize the bone with global thresholds, denoise with a Gaussian filter, 
        and remove small bone particles less than 420 voxels (0.094 mm3). 

        Args:
            img (Image)
            lower (int)
            upper (int)

        Returns:
            Image
        """
        sigma_over_spacing = img.GetSpacing()[0]

        # gaussian smoothing filter
        print("Applying Gaussian filter")
        gaussian_filter = sitk.SmoothingRecursiveGaussianImageFilter()
        gaussian_filter.SetSigma(sigma_over_spacing)
        gaussian_img = gaussian_filter.Execute(img)

        thresh_img = sitk.BinaryThreshold(gaussian_img, 
                                          lowerThreshold=lower,
                                          upperThreshold=upper,
                                          insideValue=1)

        # remove bone particles less than 420 voxels in size
        connected_filter = sitk.ConnectedComponentImageFilter()
        connect_img = connected_filter.Execute(thresh_img)
        label_img = sitk.RelabelComponent(connect_img, minimumObjectSize=420)
        thresh_img = sitk.BinaryThreshold(label_img,
                                          lowerThreshold=1,
                                          upperThreshold=10000,
                                          insideValue=1)
        return thresh_img

    def createROI(self, thresh_img):
        """
        Label voids in the bone and background as ROI.

        Args:
            thresh_img (Image)

        Returns:
            Image: All voids inside ROI are marked with the value 1, 
                   and all other regions are marked with 0.  
        """

        # invert to select background and voids in the bone
        invert_filter = sitk.InvertIntensityImageFilter()
        invert_filter.SetMaximum(1)
        void_volume_img = invert_filter.Execute(thresh_img)

        void_volume_img = self.contour_img * void_volume_img

        return void_volume_img

    def distanceVoidVolume(self, void_volume_img, radius):
        """
        Select voids of large diameter. 

        Args:
            void_volume_img (Image)
            radius (int): minimum radius of the erosions to be selected, in voxels

        Returns:
            Image
        """
        distance_filter = sitk.SignedMaurerDistanceMapImageFilter()
        distance_filter.SetSquaredDistance(False)
        distance_filter.SetBackgroundValue(1)
        inner_img = distance_filter.Execute(void_volume_img)

        inner_img = sitk.BinaryThreshold(inner_img,
                                        lowerThreshold=1,
                                        upperThreshold=radius,
                                        insideValue=1)
        inner_img = void_volume_img - inner_img

        distance_filter.SetBackgroundValue(0)
        outer_img = distance_filter.Execute(inner_img)

        outer_img = sitk.BinaryThreshold(outer_img,
                                         lowerThreshold=1,
                                         upperThreshold=radius,
                                         insideValue=1)
        distance_img = outer_img + inner_img

        return distance_img

    def erodeVoidVolume(self, void_volume_img, radius):
        """
        Morphologically erode voids to remove connections and to
        prevent erosions from leaking into the trabecular region.

        Args:
            void_volume_img (Image)
            radius (int): erode steps, in voxels
        
        Returns:
            Image
        """
        print("Applying erode filter")
        erode_filter = sitk.BinaryErodeImageFilter()
        erode_filter.SetForegroundValue(1)
        erode_filter.SetKernelRadius([radius,radius,radius])
        erode_img = erode_filter.Execute(void_volume_img)

        return erode_img

    def connectVoidVolume(self, erode_img):
        """
        Label voids that are connected to seed points.

        Args:
            erode_img (Image)
        Returns:
            Image
        """
        seeds_img = sitk.Image(self.contour_img.GetSize(), sitk.sitkUInt8)
        seeds_img.CopyInformation(self.contour_img)
        for seed in self.seeds:
            seeds_img[seed] = 1

        # apply distance transformation to the seed points
        print("Applying distance map filter")
        distance_filter = sitk.SignedMaurerDistanceMapImageFilter()
        distance_filter.SetSquaredDistance(False)
        distance_filter.SetBackgroundValue(0)
        distance_img = distance_filter.Execute(seeds_img)

        # inflate seed points by 5 voxels
        radius = 5
        seeds_img = sitk.BinaryThreshold(distance_img, 
                                         lowerThreshold=0, 
                                         upperThreshold=radius, 
                                         insideValue=1)

        # combine inflated seed points and voids in the bone
        void_seeds_img = seeds_img | erode_img

        # connected threshold filter to select voids connected to seed points
        connected_filter = sitk.ConnectedThresholdImageFilter()
        connected_filter.SetLower(1)
        connected_filter.SetUpper(1)
        connected_filter.SetSeedList(self.seeds)
        connected_filter.SetReplaceValue(1)
        connected_img = connected_filter.Execute(void_seeds_img)
        
        # remove inflated seed points from the voids
        connected_img = erode_img * connected_img

        return connected_img

    def dilateVoidVolume(self, connect_img, radius):
        """
        Morphologically dilate voids back to their original size.

        Args:
            connect_img (Image)
            radius (Image): dilate steps, in voxels

        Returns:
            Image
        """
        print("Applying dilate filter")
        dilate_filter = sitk.BinaryDilateImageFilter()
        dilate_filter.SetForegroundValue(1)
        dilate_filter.SetKernelRadius([radius,radius,radius])
        dilate_img = dilate_filter.Execute(connect_img)

        # apply mask to dilated voids to get volumes only inside the 
        #  endosteal boundary
        void_volume_img = dilate_img * self.contour_img

        return void_volume_img

    def combineVoidVolume(self, ero1_img, ero2_img, radius):
        """
        Combine two erosion labels by dilating the first one and masking it with the second one.

        Args:
            ero1_img (Image)
            ero2_img (Image): should occupy the same physical space as ero1_img
            radius (Int): dilate steps, in voxels

        Returns:
            Image
        """
        dilate_filter = sitk.BinaryDilateImageFilter()
        dilate_filter.SetForegroundValue(1)
        dilate_filter.SetKernelRadius([radius,radius,radius])
        dilate_img = dilate_filter.Execute(ero1_img)

        # mask ero2 onto ero1
        output_img = dilate_img * ero2_img

        connected_filter = sitk.ConnectedThresholdImageFilter()
        connected_filter.SetReplaceValue(1)
        connected_filter.SetUpper(1)
        connected_filter.SetLower(1)
        connected_filter.SetSeedList(self.seeds)
        output_img = connected_filter.Execute(output_img)

        return output_img

    def labelVoidVolume(self, void_volume_img):
        """
        Label separate erosions with different labels. Small particles are removed. 

        Args:
            void_volume_img (Image)
        
        Returns:
            Image
        """
        # connected component filter and relabel filter
        connected_cmp_filter = sitk.ConnectedComponentImageFilter()
        connected_cmp_img = connected_cmp_filter.Execute(void_volume_img)
        label_img = sitk.RelabelComponent(connected_cmp_img, minimumObjectSize=927)
        return label_img

    def execute(self):
        """
        Execute the next step in the algorithm.

        Returns:
            bool: False if reached the end of the algorithm, True otherwise. 
        """
        self._step += 1
        try:
            if self._step == 1:
                self._cleanup()
                self.model_img = self.smoothen(self.model_img, self.lower_threshold, self.upper_threshold)
            elif self._step == 2:
                self.ero2_img = self.createROI(self.model_img)
            elif self._step == 3:
                self.ero1_img = self.distanceVoidVolume(self.ero2_img, self.minimalRadius)
            elif self._step == 4:
                self.ero1_img = self.erodeVoidVolume(self.ero1_img, self.morphologicalRadius)
            elif self._step == 5:
                self.ero1_img = self.connectVoidVolume(self.ero1_img)
            elif self._step == 6:
                self.ero1_img = self.dilateVoidVolume(self.ero1_img, self.morphologicalRadius)
            elif self._step == 7:
                radius = 3 if self.morphologicalRadius > 5 else 5
                self.output_img = self.combineVoidVolume(self.ero1_img, self.ero2_img, radius)
            elif self._step == 8:
                self.output_img = self.labelVoidVolume(self.output_img)
            else: # the end of the algorithm
                self._step = 0
                return False

            return True
        except:
            self._step = 0
            raise   

    def setModelImage(self, img):
        """
        Args:
            img (Image)
        """
        self.model_img = img
    
    def setContourImage(self, contour_img):
        """
        Args:
            contour_img (Image)
        """
        # threshhold to binarize mask
        thresh_img = sitk.BinaryThreshold(contour_img,
                                          lowerThreshold=1,
                                          insideValue=1)
        
        # paste mask to a blank image that matches the size of the scan
        #  this step is to make sure mask lies in the same physical space as the scan
        img_width = self.model_img.GetWidth()
        img_height = self.model_img.GetHeight()
        img_depth = self.model_img.GetDepth()
        img_spacing = self.model_img.GetSpacing()[0]
        self.contour_img = sitk.Image(img_width, img_height, img_depth, sitk.sitkUInt8)
        self.contour_img.CopyInformation(self.model_img)
        destination_index = (int(thresh_img.GetOrigin()[0]/img_spacing),
                             int(thresh_img.GetOrigin()[1]/img_spacing),
                             int(thresh_img.GetOrigin()[2]/img_spacing))
        source_size = thresh_img.GetSize()
        paste_filter = sitk.PasteImageFilter()
        paste_filter.SetDestinationIndex(destination_index)
        paste_filter.SetSourceSize(source_size)
        self.contour_img = paste_filter.Execute(self.contour_img, thresh_img)

    def setThresholds(self, lower_threshold, upper_threshold):
        """
        Args:
            lower_threshold (int)
            upper_threshold (int)
        """
        self.lower_threshold = lower_threshold
        self.upper_threshold = upper_threshold

    def setSeeds(self, seeds):
        """
        Args:
            seeds (list of list/tuple of int)
        """
        self.seeds = seeds

    def setRadii(self, minimalRadius, morphologicalRadius):
        """
        Args:
            minimalRadius (int): minimum erosion radius, used in the distance map filter
            morphologicalRadius (int): kernel radius for dilate/erode filters
        """
        self.minimalRadius = minimalRadius
        self.morphologicalRadius = morphologicalRadius
    
    def _cleanup(self):
        """
        Reset internal parameters.
        """
        pass

    def getOutput(self):
        return self.output_img


# execute this script on command line
if __name__ == "__main__":
    import argparse

    # Read the input arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('inputImage', help='The input scan file path')
    parser.add_argument('inputMask', help='The input mask file path')
    parser.add_argument('outputImage', help='The output image file path')
    parser.add_argument('seeds', help='The seed points csv file path')
    parser.add_argument('lowerThreshold', type=int)
    parser.add_argument('upperThreshold', type=int)
    parser.add_argument('minimalRadius', type=int, nargs='?', default=3, 
                        help='Minimal erosion radius in voxels, default=3')
    parser.add_argument('morphologicalRadius', type=int, nargs='?', default=5,
                        help='Morphological kernel radius in voxels, default=5')
    args = parser.parse_args()

    input_dir = args.inputImage
    mask_dir = args.inputMask
    output_dir = args.outputImage
    seeds_dir = args.seeds
    lower = args.lowerThreshold
    upper = args.upperThreshold
    minimalRadius = args.minimalRadius
    morphologicalRadius = args.morphologicalRadius

    # read images
    img = sitk.ReadImage(input_dir)
    mask = sitk.ReadImage(mask_dir)
    # read seadpoints
    seeds = []
    HEADER = 3
    lineCount = 0
    with open(seeds_dir) as fcsv:
        for line in fcsv:
            # line = 'id,x,y,z,ow,ox,oy,oz,vis,sel,lock,label,desc,associatedNodeID'
            if lineCount >= HEADER:
                seed = line.split(',')
                x = int(float(seed[1]))
                y = int(float(seed[2]))
                z = int(float(seed[3]))
                seeds.append((x,y,z))
            lineCount += 1

    # create erosion logic object
    erosion = VoidVolumeLogic(img, mask, lower, upper, seeds, 
                              minimalRadius, morphologicalRadius)

    # identify erosions
    print("Running erosion detection script")
    while (erosion.execute()):
        pass
    erosion_img = erosion.getOutput()

    # store erosions
    print("Storing image in {}".format(output_dir))
    sitk.WriteImage(erosion_img, output_dir)
