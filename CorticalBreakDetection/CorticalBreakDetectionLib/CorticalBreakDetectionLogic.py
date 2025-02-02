#-----------------------------------------------------
# ErosionDetectionLogic.py
#
# Created by:  Mingjie Zhao
# Created on:  23-07-2021
#
# Description: This module contains the logics class 
#              for the 3D Slicer Cortical Break Detection extension.
#
#-----------------------------------------------------
import slicer
from slicer.ScriptedLoadableModule import *
import vtk
import SimpleITK as sitk
import sitkUtils
import logging, os
import numpy as np
from .PetersCorticalBreakDetectionLogic import PetersCorticalBreakDetectionLogic
from .CBCTCorticalBreakDetectionLogic import CBCTCorticalBreakDetectionLogic

#
# CorticalBreakDetectionLogic
#
class CorticalBreakDetectionLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
  computation done by your module. 
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self):
    # initialize call back object for updating progrss bar
    self.progressCallBack = None

    self.CorticalBreakDetection = PetersCorticalBreakDetectionLogic()

  def IJKToRASCoords(self, ijk_3coords, ijk2ras):
    """
    Convert from SimpleITK coordinates to IJK coordinates. 
    Normally this involves negating the x, y coordinates, 
    and scaling the coordinates with respect to the spacing. 

    Args:
      ijk_3coords (list of Int)
      ijk2ras (vtkMatrix4x4): 4 by 4 matrix that converts from IJK to RAS

    Returns:
      tuple of int
    """
    ijk_4coords = ijk_3coords + [1]
    return tuple((i for i in ijk2ras.MultiplyPoint(ijk_4coords)[:3]))
  
  def setDefaultDirectory(self, inputVolumeNode):
    """
    Set the default directory to be the same as where the inputVolumeNode is stored.
    Files created after this method is called will be saved in that directory.

    Args:
      inputVolumeNode (vtkMRMLScalarVolumeNode)
    """
    storageNode = inputVolumeNode.GetStorageNode()
    if storageNode:
      dir = os.path.dirname(storageNode.GetFullNameFromFileName())
      slicer.mrmlScene.SetRootDirectory(dir)
      
  def setSegmentParameters(self, inputVolumeNode, sigma:int, method:int=None, lower:int=None, upper:int=None) -> bool:
    if method is None:
      # check input validity
      if (lower > upper):
        slicer.util.errorDisplay('Lower threshold cannot be greater than upper threshold.')
        return False

    # images
    model_img = sitkUtils.PullVolumeFromSlicer(inputVolumeNode.GetName())
    self.CorticalBreakDetection.setModel(model_img)
    
    # thresholds
    if method is not None:
      self.CorticalBreakDetection.setMethod(method)
    else:
      self.CorticalBreakDetection.setThresholds(lower, upper)

    # sigma
    self.CorticalBreakDetection.setSigma(sigma)

    return True

  def segment(self, outputVolumeNode):
    """
    Segment the input Volume and store the result in output volume.
    
    Args:
      outputVolumeNode (vtkMRMLLabelMapVolumeNode

    Returns:
      bool: True for success, False otherwise
    """
    logging.info('Segmenting started')
    
    # run erosion detection algorithm
    try:
      step = 1
      self.CorticalBreakDetection.execute(step)
    except Exception as e:
      slicer.util.errorDisplay('Error')
      print(e)
      return False
    segmented_img = self.CorticalBreakDetection.getSeg()

    logging.info('Processing completed')

    sitkUtils.PushVolumeToSlicer(segmented_img, outputVolumeNode)

    return True

  def setCorticalBreaksParameters(self, lower, upper, inputVolumeNode, inputBoneNode, maskNode, 
                                  outputCorticalBreaksNode, outputErosionsNode, corticalThickness, dilateErodeDistance, 
                                  voxelSize, cbCT):
    """
    Set parameters for automatic cortical break detection algorithm.
    
    Args:
      lower (int)
      upper (int)
      inputVolumeNode (vtkMRMLInputVolumeNode)
      inputBoneNode (vtkMRMLLabelMapVolumeNode)
      maskNode (vtkMRMLLabelMapVolumeNode)
      outputCorticalBreaksNode (vtkMRMLLabelMapVolumeNode)
      outputErosionsNode (vtkMRMLLabelMapVolumeNode)
      corticalThickness (Int)
      dilateErodeDistance (Int)
      voxelSize (Float)
      cbCT (bool): whether to use the original method or the CBCT version 
                   of the cortical break detection algorithm.

    Returns:
      bool: True if success, False otherwise
    """
    if outputCorticalBreaksNode:
      if (inputBoneNode.GetID() == outputCorticalBreaksNode.GetID() or
          maskNode.GetID() == outputCorticalBreaksNode.GetID()):
        slicer.util.errorDisplay('Input volume is the same as output volume. Select a different output volume.')
        return False
    if outputErosionsNode:
      if (inputBoneNode.GetID() == outputErosionsNode.GetID() or
          maskNode.GetID() == outputErosionsNode.GetID()):
        slicer.util.errorDisplay('Input volume is the same as output volume. Select a different output volume.')
        return False

    if (lower > upper):
      slicer.util.errorDisplay('Lower threshold cannot be greater than upper threshold.')
      return False

    if cbCT: # only the CBCT version of the cortical break detection algorithm requires greyscale image
      self.CorticalBreakDetection = CBCTCorticalBreakDetectionLogic()
    else:
      self.CorticalBreakDetection = PetersCorticalBreakDetectionLogic()

    # images
    seg_img = sitkUtils.PullVolumeFromSlicer(inputBoneNode.GetName())
    self.CorticalBreakDetection.setSeg(seg_img)
    mask_img = sitkUtils.PullVolumeFromSlicer(maskNode.GetName())
    self.CorticalBreakDetection.setContour(mask_img)
    model_img = sitkUtils.PullVolumeFromSlicer(inputVolumeNode.GetName())
    self.CorticalBreakDetection.setModel(model_img)
    
    # distances
    self.CorticalBreakDetection.setCorticalThickness(corticalThickness)
    self.CorticalBreakDetection.setDilateErodeDistance(dilateErodeDistance)

    # thresholds
    self.CorticalBreakDetection.setThresholds(lower, upper)
    self.CorticalBreakDetection.setVoxelSize(voxelSize*1000)

    return True

  def getCorticalBreaks(self, outputCorticalBreaksNode, outputErosionsNode, noProgress=False):
    """
    Run the automatic cortical break detection algorithm.

    Args:
      outputCorticalBreakDetectionsNode (vtkMRMLLabelMapVolumeNode)
    """
    # initialize progress bar
    increment = 100 // self.CorticalBreakDetection.stepNum # progress bar increment value
    progress = increment                          # progress bar initial value
    if not noProgress:
      self.progressCallBack(progress)
    logging.info('Processing started')
    
    # run erosion detection algorithm
    try:
      step = 2
      while (self.CorticalBreakDetection.execute(step)): # execute the next step
        progress += increment
        if not noProgress:
          self.progressCallBack(progress) # update progress bar
        step += 1
    except Exception as e:
      slicer.util.errorDisplay('Error')
      print(e)
      return False
    cortical_breaks = self.CorticalBreakDetection.getOutputBreaks()
    erosions = self.CorticalBreakDetection.getOutputErosions()

    logging.info('Processing completed')

    if outputCorticalBreaksNode:
      sitkUtils.PushVolumeToSlicer(cortical_breaks, outputCorticalBreaksNode)
    if outputErosionsNode:
      sitkUtils.PushVolumeToSlicer(erosions, outputErosionsNode)

    return True

  def getSeeds(self, inputBoneNode, fiducialNode):
    """
    Convert the cortical break masks into seed points.

    Args:
      inputBoneNode (vtkMRMLLabelMapVolumeNode)
      fiducialNode (vtkMRMLMarkupsFiducialNode)
    """
    ijk2ras = vtk.vtkMatrix4x4()
    inputBoneNode.GetIJKToRASMatrix(ijk2ras)

    fiducialNode.RemoveAllMarkups()

    for seed in self.CorticalBreakDetection.getSeeds():
      ras_coord = self.IJKToRASCoords(list(seed), ijk2ras)
      fiducialNode.AddFiducialFromArray(ras_coord)

  def intensityCheck(self, volumeNode):
    '''
    Check if image intensity units are in HU

    Args:
      volumeNode (vtkMRMLVolumeNode)
    
    Returns:
      bool: True for HU units, false for other
    '''
    #create array and calculate statistics
    arr = slicer.util.arrayFromVolume(volumeNode)
    arr_max = np.where(arr > 4000, arr, 0)
    max_ratio = np.count_nonzero(arr_max) / arr.size
    arr_min = np.where(arr < -1000, arr, 0)
    min_ratio = np.count_nonzero(arr_min) / arr.size
    arr_avg = np.average(arr)
    arr_std = np.std(arr)

    #checks: 
    #-1000 < average < 1000
    #500 < standard deviation < 1000
    #out of range values < 10% of image
    return (arr_avg > -1000 and arr_avg < 1000 and arr_std > 500 and arr_std < 1000 and max_ratio + min_ratio < 0.1)