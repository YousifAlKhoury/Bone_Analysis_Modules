#-----------------------------------------------------
# Training.py
#
# Created by:  Yousif Al-Khoury
# Created on:  12-12-2022
#
# Description: This module sets up the interface for the Erosion Volume 3D Slicer extension.
#
#-----------------------------------------------------
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging
from TrainingLib.ErosionVolumeLogic import ErosionVolumeLogic
from TrainingLib.MarkupsTable import MarkupsTable
import os

import SimpleITK as sitk
import sitkUtils

#
# ErosionVolume
#
class Training(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Training" # TODO make this more human readable by adding spaces
    self.parent.categories = ["Bone Analysis Module (BAM)"]
    self.parent.dependencies = []
    self.parent.contributors = ["Yousif Al-Khoury"] # replace with "Firstname Lastname (Organization)"
    self.parent.helpText = """ 
TODO
"""
    self.parent.helpText += "<br>For more information see the <a href=https://github.com/ManskeLab/3DSlicer_Erosion_Analysis/wiki/Erosion-Volume-Module>online documentation</a>."
    self.parent.helpText += "<br><td><img src=\"" + self.getLogo('bam') + "\" height=80> "
    self.parent.helpText += "<img src=\"" + self.getLogo('manske') + "\" height=80></td>"
    self.parent.acknowledgementText = """
    
Updated on December 12, 2022.<br>
Manske Lab<br>
    McCaig Institue for Bone and Joint Health<br>
    University of Calgary
""" # replace with organization, grant and thanks.

  def getLogo(self, logo_type):
    #get directory
    directory = os.path.split(os.path.split(os.path.realpath(__file__))[0])[0]

    #set file name
    if logo_type == 'bam':
      name = 'BAM_Logo.png'
    elif logo_type == 'manske':
      name = 'Manske_Lab_Logo.png'

    #
    if '\\' in directory:
      return directory + '\\Logos\\' + name
    else:
      return directory + '/Logos/' + name

#
# ErosionVolumeWidget
#
class TrainingWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """
  def __init__(self, parent):
    # Initialize logics object
    self._logic = ErosionVolumeLogic()
    # initialize call back object for updating progrss bar
    self._logic.progressCallBack = self.setProgress

    self.images_dir = os.path.join(os.path.split(os.path.dirname(os.path.abspath(__file__)))[0], 'ACTUS_HRQPCT')
    self.seed_points_dir = os.path.join(self.images_dir, 'SeedPoints')
    self.reference_erosions_dir = os.path.join(self.images_dir, 'ErosionSegs')
    self.images_dir = os.path.join(self.images_dir, 'TestFiles')

    ScriptedLoadableModuleWidget.__init__(self, parent)

  def setup(self):
    # Buttons for testing
    ScriptedLoadableModuleWidget.setup(self)

    self.warning = qt.QLabel(
      """WARNING: This module clears all current nodes in the current slicer scene, <br>
      including those worked on inside other modules. Please save your work <br>
      before pressing the 'Proceed' button below.""")
    self.layout.addWidget(self.warning)
    self.proceedButton = qt.QPushButton("Proceed")
    self.proceedButton.toolTip = "Warning before proceeding with the training module."
    self.proceedButton.setFixedSize(80, 25)
    self.layout.addWidget(self.proceedButton)
    self.proceedButton.clicked.connect(self.proceed)
    self.layout.addStretch(0)

    # slicer.mrmlScene.Clear(True)

  def proceed(self):
    self.proceedButton.deleteLater()
    self.warning.deleteLater()
    # Collapsible buttons
    self.erosionsCollapsibleButton = ctk.ctkCollapsibleButton()

    slicer.mrmlScene.Clear(False)

    for image in os.listdir(self.images_dir):
      if not ('mha' in image):
        continue
      image = os.path.join(self.images_dir, image)
      slicer.util.loadVolume(image)

    for markup in os.listdir(self.seed_points_dir):
      if not ('json' in markup):
        continue
      markup = os.path.join(self.seed_points_dir, markup)
      markupsNode = slicer.util.loadMarkups(markup)
      markupsNode.SetDisplayVisibility(False)

    # Set up widgets inside the collapsible buttons
    self.setupErosions()

    # Add vertical spacer
    self.layout.addStretch(1)

    # Update buttons
    self.checkErosionsButton()
    self.onSelectInputVolume()

  def setupErosions(self):
    """Set up widgets in step 4 erosions"""
    # Set text on collapsible button, and add collapsible button to layout
    self.erosionsCollapsibleButton.text = "Training"
    self.layout.addWidget(self.erosionsCollapsibleButton)

    # Layout within the collapsible button
    erosionsLayout = qt.QFormLayout(self.erosionsCollapsibleButton)
    erosionsLayout.setVerticalSpacing(5)

    # input volume selector
    self.inputVolumeSelector = slicer.qMRMLNodeComboBox()
    self.inputVolumeSelector.nodeTypes = ["vtkMRMLScalarVolumeNode"]
    self.inputVolumeSelector.selectNodeUponCreation = False
    self.inputVolumeSelector.addEnabled = False
    self.inputVolumeSelector.renameEnabled = True
    self.inputVolumeSelector.removeEnabled = True
    self.inputVolumeSelector.noneEnabled = False
    self.inputVolumeSelector.showHidden = False
    self.inputVolumeSelector.showChildNodeTypes = False
    self.inputVolumeSelector.setMRMLScene(slicer.mrmlScene)
    self.inputVolumeSelector.setToolTip( "Pick the greyscale scan" )
    self.inputVolumeSelector.setCurrentNode(None)
    erosionsLayout.addRow("Input Volume: ", self.inputVolumeSelector)

    # input contour selector
    self.inputContourSelector = slicer.qMRMLNodeComboBox()
    self.inputContourSelector.nodeTypes = ["vtkMRMLScalarVolumeNode","vtkMRMLLabelMapVolumeNode"]
    self.inputContourSelector.selectNodeUponCreation = False
    self.inputContourSelector.addEnabled = False
    self.inputContourSelector.renameEnabled = True
    self.inputContourSelector.removeEnabled = True
    self.inputContourSelector.noneEnabled = False
    self.inputContourSelector.showHidden = False
    self.inputContourSelector.showChildNodeTypes = False
    self.inputContourSelector.setMRMLScene(slicer.mrmlScene)
    self.inputContourSelector.setToolTip( "Pick the mask label map" )
    self.inputContourSelector.setCurrentNode(None)
    erosionsLayout.addRow("Input Contour: ", self.inputContourSelector)

    # output volume selector
    self.outputErosionSelector = slicer.qMRMLNodeComboBox()
    self.outputErosionSelector.nodeTypes = ["vtkMRMLSegmentationNode"]
    self.outputErosionSelector.selectNodeUponCreation = True
    self.outputErosionSelector.addEnabled = True
    self.outputErosionSelector.removeEnabled = True
    self.outputErosionSelector.renameEnabled = True
    self.outputErosionSelector.noneEnabled = False
    self.outputErosionSelector.showHidden = False
    self.outputErosionSelector.showChildNodeTypes = False
    self.outputErosionSelector.setMRMLScene(slicer.mrmlScene)
    self.outputErosionSelector.baseName = "ER"
    self.outputErosionSelector.setToolTip( "Pick the output segmentation to store the erosions in" )
    self.outputErosionSelector.setCurrentNode(None)
    erosionsLayout.addRow("Output Erosions: ", self.outputErosionSelector)

    # threshold spin boxes (default unit is HU)
    self.lowerThresholdText = qt.QSpinBox()
    self.lowerThresholdText.setMinimum(-9999)
    self.lowerThresholdText.setMaximum(999999)
    self.lowerThresholdText.setSingleStep(10)
    self.lowerThresholdText.value = 850
    erosionsLayout.addRow("Lower Threshold: ", self.lowerThresholdText)
    self.upperThresholdText = qt.QSpinBox()
    self.upperThresholdText.setMinimum(-9999)
    self.upperThresholdText.setMaximum(999999)
    self.upperThresholdText.setSingleStep(10)
    self.upperThresholdText.value = 9999
    erosionsLayout.addRow("Upper Threshold: ", self.upperThresholdText)

    # gaussian sigma spin box
    self.sigmaText = qt.QDoubleSpinBox()
    self.sigmaText.setMinimum(0.0001)
    self.sigmaText.setDecimals(4)
    self.sigmaText.value = 1
    self.sigmaText.setToolTip("Standard deviation in the Gaussian smoothing filter")
    erosionsLayout.addRow("Gaussian Sigma: ", self.sigmaText)

    # seed point table
    self.markupsTableWidget = MarkupsTable(self.erosionsCollapsibleButton)
    self.markupsTableWidget.setMRMLScene(slicer.mrmlScene)
    self.markupsTableWidget.setNodeSelectorVisible(True) # use the above selector instead
    self.markupsTableWidget.setButtonsVisible(False)
    self.markupsTableWidget.setPlaceButtonVisible(True)
    self.markupsTableWidget.setDeleteAllButtonVisible(True)
    self.markupsTableWidget.setJumpToSliceEnabled(True)

    # horizontal white space
    erosionsLayout.addRow(qt.QLabel(""))

    # check box for Large erosions
    self.LargeErosionsCheckBox = qt.QCheckBox('Large Erosions')
    self.LargeErosionsCheckBox.checked = False
    self.LargeErosionsCheckBox.setToolTip('Set internal parameters for segmenting large erosions')
    erosionsLayout.addRow(self.LargeErosionsCheckBox)

    # check box for CBCT scans
    self.SmallErosionsCheckBox = qt.QCheckBox('Small Erosions')
    self.SmallErosionsCheckBox.checked = False
    self.SmallErosionsCheckBox.setToolTip('Set internal parameters for segmenting small erosions')
    erosionsLayout.addRow(self.SmallErosionsCheckBox)

    # glyph size 
    self.glyphSizeBox = qt.QDoubleSpinBox()
    self.glyphSizeBox.setMinimum(0.5)
    self.glyphSizeBox.setMaximum(25)
    self.glyphSizeBox.setSingleStep(0.5)
    self.glyphSizeBox.setSuffix(' %')
    self.glyphSizeBox.value = 1.0
    erosionsLayout.addRow("Seed Point Size ", self.glyphSizeBox)

    # advanced parameter spin boxes
    self.minimalRadiusText = 3
    self.dilateErodeDistanceText = 4

    # Execution layout
    executeGridLayout = qt.QGridLayout()
    executeGridLayout.setRowMinimumHeight(0,15)
    executeGridLayout.setRowMinimumHeight(1,15)

    # Progress Bar
    self.progressBar = qt.QProgressBar()
    self.progressBar.hide()
    executeGridLayout.addWidget(self.progressBar, 0, 0)

    # Get Erosion Button
    self.getErosionsButton = qt.QPushButton("Get Erosions")
    self.getErosionsButton.toolTip = "Get erosions stored in a label map"
    self.getErosionsButton.enabled = False
    executeGridLayout.addWidget(self.getErosionsButton, 1, 0)

    # Execution frame with progress bar and get button
    erosionButtonFrame = qt.QFrame()
    erosionButtonFrame.setLayout(executeGridLayout)
    erosionsLayout.addRow(erosionButtonFrame)
    
    # connections
    self.erosionsCollapsibleButton.connect("contentsCollapsed(bool)", self.onCollapsed4)
    self.inputVolumeSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.checkErosionsButton)
    self.inputVolumeSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onSelectInputVolume)
    self.inputContourSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onSelectInputContour)
    self.inputContourSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.checkErosionsButton)
    self.outputErosionSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.checkErosionsButton)
    self.outputErosionSelector.connect("nodeAddedByUser(vtkMRMLNode*)", lambda node: self.onAddOutputErosion(node))
    self.markupsTableWidget.getMarkupsSelector().connect("currentNodeChanged(vtkMRMLNode*)", self.checkErosionsButton)
    self.markupsTableWidget.getMarkupsSelector().connect("currentNodeChanged(vtkMRMLNode*)", self.onSelectSeed)
    self.LargeErosionsCheckBox.connect("clicked(bool)", self.onLargeErosionsChecked)
    self.SmallErosionsCheckBox.connect("clicked(bool)", self.onSmallErosionsChecked)
    self.glyphSizeBox.valueChanged.connect(self.onGlyphSizeChanged)
    self.getErosionsButton.connect("clicked(bool)", self.onGetErosionsButton)

    # logger
    self.logger = logging.getLogger("erosion_volume")

  def checkErosionsButton(self):
    self.getErosionsButton.enabled = (self.inputVolumeSelector.currentNode() and 
                                     self.inputContourSelector.currentNode() and
                                     self.outputErosionSelector.currentNode() and
                                     self.markupsTableWidget.getCurrentNode())

  def onSelect4(self):
    """Update the state of the get erosions button whenever the selectors in step 4 change"""
    self.getErosionsButton.enabled = (self.inputVolumeSelector.currentNode() and 
                                     self.inputContourSelector.currentNode() and
                                     self.outputErosionSelector.currentNode() and
                                     self.markupsTableWidget.getCurrentNode())

  def onSelectInputVolume(self):
    """Run this whenever the input volume selector in step 4 changes"""
    inputVolumeNode = self.inputVolumeSelector.currentNode()
    inputContourNode = self.inputContourSelector.currentNode()

    if inputVolumeNode:
      # Update the default save directory
      self._logic.setDefaultDirectory(inputVolumeNode)

      # Update the spacing scale in the seed point table
      ras2ijk = vtk.vtkMatrix4x4()
      ijk2ras = vtk.vtkMatrix4x4()
      inputVolumeNode.GetRASToIJKMatrix(ras2ijk)
      inputVolumeNode.GetIJKToRASMatrix(ijk2ras)
      self.markupsTableWidget.setCoordsMatrices(ras2ijk, ijk2ras)
      # update the viewer windows
      slicer.util.setSliceViewerLayers(background=inputVolumeNode)
      slicer.util.resetSliceViews() # centre the volume in the viewer windows

      #Set master volume in statistics step
      self.masterVolumeSelector.setCurrentNode(inputVolumeNode)
      self.voxelSizeText.value = inputVolumeNode.GetSpacing()[0]

      #check if preset intensity units exist
      check = True
      if "Lower" in inputVolumeNode.__dict__.keys():
        self.lowerThresholdText.setValue(inputVolumeNode.__dict__["Lower"])
        check = False
      if "Upper" in inputVolumeNode.__dict__.keys():
        self.upperThresholdText.setValue(inputVolumeNode.__dict__["Upper"])
        check = False

      #check intensity units and display warning if not in HU
      if check and not self.threshButton.checked:
        if not self._logic.intensityCheck(inputVolumeNode):
          text = """The selected image likely does not use HU for intensity units. 
Default thresholds are set in HU and will not generate an accurate result. 
Change the lower and upper thresholds before initializing."""
          slicer.util.warningDisplay(text, windowTitle='Intensity Unit Warning')

      #remove existing loggers
      if self.logger.hasHandlers():
        for handler in self.logger.handlers:
          self.logger.removeHandler(handler)
          
       #initialize logger with filename
      try:
        filename = inputVolumeNode.GetStorageNode().GetFullNameFromFileName()
        filename = os.path.split(filename)[0] + '/LOG_' + os.path.split(filename)[1]
        filename = os.path.splitext(filename)[0] + '.log'
      except:
        filename = 'share/' + inputVolumeNode.GetName() + '.'
      logHandler = logging.FileHandler(filename)
      
      self.logger.addHandler(logHandler)
      self.logger.info("Using Erosion Volume Module with " + inputVolumeNode.GetName() + "\n")

      #set name in statistics
      self.masterVolumeSelector.baseName = inputVolumeNode.GetName()
      

  def onSelectInputContour(self):
    """Run this whenever the input contour selector in step 4 changes"""
    inputContourNode = self.inputContourSelector.currentNode()
    if inputContourNode:
      # update the default output erosion base name, which matches the mask name
      erosion_baseName = inputContourNode.GetName()+"_ER"
      self.outputErosionSelector.baseName = erosion_baseName
      self.segmentCopier.currSegmentationSelector.baseName = erosion_baseName
      self.segmentCopier.otherSegmentationSelector.baseName = erosion_baseName
      self.segmentationSelector.baseName = erosion_baseName
      self.inputErosionSelector.baseName = erosion_baseName
      seed_baseName = inputContourNode.GetName()+"_SEEDS"
      # self.fiducialSelector.baseName = seed_baseName
      self.outputTableSelector.baseName = inputContourNode.GetName()+"_TABLE"
      

  def onAddOutputErosion(self, node):
    """Run this whenever a new erosion segmentation is created from the selector in step 4"""
    # force the output erosion base name to have the post fix '_' plus an index
    #  i.e. baseName_1, baseName_2, ...
    baseName = node.GetName()
    index_str = baseName.split('_')[-1]
    if not index_str.isdigit(): # not postfixed with '_' plus an index
      node.SetName(slicer.mrmlScene.GenerateUniqueName(baseName))

  def onSelectSeed(self):
    """Run this whenever the seed point selector in step 4 changes"""
    self.markupsTableWidget.onMarkupsNodeChanged()
    markupsDisplayNode = self.markupsTableWidget.getCurrentNode().GetMarkupsDisplayNode()
    markupsDisplayNode.SetGlyphScale(self.glyphSizeBox.value)

  def onLargeErosionsChecked(self):
    """Run this whenever the check box for Large Erosions in step 4 changes"""
    if self.LargeErosionsCheckBox.checked:
      self.minimalRadiusText = 6
      self.dilateErodeDistanceText = 6
      self.SmallErosionsCheckBox.checked = False
    else:
      self.minimalRadiusText = 3
      self.dilateErodeDistanceText = 4

  def onSmallErosionsChecked(self):
    """Run this whenever the check box for Small Erosions in step 4 changes"""
    if self.SmallErosionsCheckBox.checked:
      self.minimalRadiusText = 2
      self.dilateErodeDistanceText = 3
      self.LargeErosionsCheckBox.checked = False
    else:
      self.minimalRadiusText = 3
      self.dilateErodeDistanceText = 4
  
  def onGlyphSizeChanged(self):
    markupsDisplayNode = self.markupsTableWidget.getCurrentNode().GetMarkupsDisplayNode()
    markupsDisplayNode.SetGlyphScale(self.glyphSizeBox.value)

  def onGetErosionsButton(self):
    """Run this whenever the get erosions button in step 4 is clicked"""
    # update widgets
    self.disableErosionsWidgets()
    self.markupsTableWidget.updateLabels()

    inputVolumeNode = self.inputVolumeSelector.currentNode()
    inputContourNode = self.inputContourSelector.currentNode()
    outputVolumeNode = self.outputErosionSelector.currentNode()
    markupsNode = self.markupsTableWidget.getCurrentNode()

    self.logger.info("Erosion Volume initialized with parameters:")
    self.logger.info("Input Volume: " + inputVolumeNode.GetName())
    self.logger.info("Input Contour: " + inputContourNode.GetName())
    self.logger.info("Output Volume: " + outputVolumeNode.GetName())
    
    self.logger.info("Lower Theshold: " + str(self.lowerThresholdText.value))
    self.logger.info("Upper Theshold: " + str(self.upperThresholdText.value))
    self.logger.info("Gaussian Sigma: " + str(self.sigmaText.value))
    
    ready = self._logic.setErosionParameters(inputVolumeNode, 
                                          inputContourNode, 
                                          self.sigmaText.value,
                                          # fiducialNode,
                                          markupsNode,
                                          self.minimalRadiusText,
                                          self.dilateErodeDistanceText,
                                          lower=self.lowerThresholdText.value,
                                          upper=self.upperThresholdText.value)
    if ready:
      success = self._logic.getErosions(inputVolumeNode, inputContourNode, outputVolumeNode)
      if success:
        # update widgets
        erosion_name = outputVolumeNode.GetName()[0:14]
        reference_path = None

        for reference in os.listdir(self.reference_erosions_dir):
          if(erosion_name in reference):
            reference_path = os.path.join(self.reference_erosions_dir, reference)

        if(reference_path):
          volumeNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLabelMapVolumeNode')
          slicer.modules.segmentations.logic().ExportVisibleSegmentsToLabelmapNode(outputVolumeNode, volumeNode) 
          erosion = sitkUtils.PullVolumeFromSlicer(volumeNode)
          erosion_reference = sitk.ReadImage(reference_path)

          labelShape = sitk.LabelShapeStatisticsImageFilter()

          labelShape.Execute(erosion)
          num_erosions = labelShape.GetNumberOfLabels()

          num_control_points = self.markupsTableWidget.getCurrentNode().GetNumberOfFiducials()

          labelShape.Execute(erosion_reference)
          ref_num_erosions = labelShape.GetNumberOfLabels()
          error_message = ""

          print("")

          if num_control_points != ref_num_erosions:
            error_message += "Error: Incorrect amount of seed points placed.\n\n"

            if(num_control_points < ref_num_erosions):
              error_message += "{} more seed point needed.\n".format(ref_num_erosions-num_control_points)
            elif(num_control_points > ref_num_erosions):
              error_message += "Too many seed point were placed, delete {} points.".format(num_control_points-ref_num_erosions)

          elif num_control_points > num_erosions:
            error_message += "Error: Erosions not identified at all placed seed points. But, correct number of seed points placed.\n\n"
            error_message += "If erosion exists at each seed points with no erosion volume, try the following:\n\n"
            error_message += "- Reposition seed point to be located deeper into the erosion.\n"
            error_message += "  Make sure the seed point is located within the mask.\n"
            error_message += "- Enable one of the large or small erosions check boxes."
            error_message += "- Increase the lower threshold in increments of 100.\n\n"
            error_message += "Otherwise, no erosion exists at that seed point. Seed point needs to be placed at a different site.\n"

          else:
            erosion = sitk.Cast(erosion, sitk.sitkFloat32)
            erosion_reference = sitk.Cast(erosion_reference, sitk.sitkFloat32)

            resampler = sitk.ResampleImageFilter()
            resampler.SetReferenceImage(erosion_reference)
            resampler.SetInterpolator(sitk.sitkLinear)
            resampler.SetDefaultPixelValue(0)
            resampler.SetTransform(sitk.Transform())

            erosion = resampler.Execute(erosion)

            filter = sitk.SimilarityIndexImageFilter()
            filter.Execute(erosion, erosion_reference)

            similarity_index = filter.GetSimilarityIndex()

            error_message += "Correct number of erosions identified.\n\n"
            error_message += "Similarity Index = {}\n\n".format(similarity_index)
            
            if(similarity_index>=0.9):
              error_message += "Seed points placed successfully!\n" 
            elif(similarity_index>=0.5):
              error_message += "Erosions locations were identified correctly however erosion volume does not match reference erosion volumes.\n\n"
              error_message += "Try the following to improve erosion detection:\n\n"
              error_message += "\t- Reposition seed point to be located deeper within the erosion.\n"
              error_message += "- If erosions look too big:\n"
              error_message += "\t- Enable large erosions check box.\n"
              error_message += "\t- Decrease lower threshold in 100 decrements.\n"
              error_message += "- If erosions look too small:\n"
              error_message += "\t- Enable small erosions check box.\n"
              error_message += "\t- Increase lower threshold in 100 increments.\n"
            else:
              error_message += "Incorrect erosions identified, erosion locations do not match reference locations.\n\n"
              error_message += "Seed points needs to be repositioned to another site on the bone.\n\n"
              error_message += "Load reference erosion segmentation file if you would liek to see the reference erosion volumes.\n"
        
        print(error_message)
        slicer.util.errorDisplay(error_message, 'Seed point Feedback')

        self.outputErosionSelector.setCurrentNodeID("") # reset the output volume selector
            
    # store thresholds 
    inputVolumeNode.__dict__["Lower"] = self.lowerThresholdText.value
    inputVolumeNode.__dict__["Upper"] = self.upperThresholdText.value

    # update widgets
    self.enableErosionsWidgets()

    self.logger.info("Finished\n")

  def enableErosionsWidgets(self):
    """Enable widgets in the erosions layout in step 4"""
    self.checkErosionsButton()
    self.progressBar.hide()

  def disableErosionsWidgets(self):
    """Disable widgets in the erosions layout in step 4"""
    self.getErosionsButton.enabled = False
    self.progressBar.show()

  def setProgress(self, value):
    """Update the progress bar"""
    self.progressBar.setValue(value)
