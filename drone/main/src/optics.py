"""
Optics provides a way to interface with the camera, and the image recognition it runs.
"""

from __future__ import annotations
from pathlib import Path
from poltergeist import catch, Result, Ok, Err
from io import TextIOWrapper
import depthai as dai # type: ignore
from typing import Any, Tuple, List
from constants import DEVELOPMENT_MODE
from enum import Enum

HEIGHT_FOV = 55
WIDTH_FOV = 69
nnPath = Path("assets/detection_model.blob")

class PadType(Enum):
    bottleDropoff = 'bottle dropoff'
    bottlePickup = 'bottle pickup'
    medkitDropoff = 'medkit dropoff'
    medkitPickup = 'medkit pickup'
    smoresDropoff = 'smores dropoff'
    smoresPickup = 'smores pickup'
    padCenter = 'pad center'

def intoPadType(input: int) -> PadType | None:
    if input == 0:
        return PadType.bottleDropoff
    elif input == 1:
        return PadType.bottlePickup
    elif input == 2:
        return PadType.medkitDropoff
    elif input == 3:
        return PadType.medkitPickup
    elif input == 4:
        return PadType.smoresDropoff
    elif input == 5:
        return PadType.smoresPickup
    elif input == 6:
        return PadType.padCenter
    else:
        return None
    
class PixelCoords:
    """
    Pixel coordinates ranging from 0.0 - 1.0, with the origin
    at the top left.
    """

    x: float
    y: float

    def __init__(self, x: float, y: float) -> None:
        self.x = x
        self.y = y

class PixelDetection:
    padType: PadType
    normalizedCoords: PixelCoords
    confidence: float

    def __init__(self, padType: PadType, normalizedCoords: PixelCoords, confidence: float) -> None:
        self.padType = padType
        self.normalizedCoords = normalizedCoords
        self.confidence = confidence

class Eye:
    videoTape: Tuple[TextIOWrapper, dai.DataOutputQueue] | None
    nnQueue: dai.DataOutputQueue
    device: dai.Device
    
    def __init__(
            self, 
            videoTape: 
            Tuple[TextIOWrapper, dai.DataOutputQueue] | None, 
            nnQueue: dai.DataOutputQueue, 
            device: dai.Device
        ) -> None:
        self.videoTape = videoTape
        self.nnQueue = nnQueue
        self.device = device

    @staticmethod
    def new(saveVideoPath: Path | None) -> Result[Eye, Exception]:
        """
        Creates an Eye. If `save_video_path` is not None, 
        H265 data from the cam will be written to the file.
        If the filepath doesnt exist, this method will create one.
        This constructor will not raise exceptions.
        """
        # Create pipeline
        # All the following configuration should not raise exceptions
        pipeline = dai.Pipeline()

        # Define sources and output
        camRgb = pipeline.create(dai.node.ColorCamera)
        detectionNetwork: dai.node.YoloDetectionNetwork = pipeline.createYoloDetectionNetwork()
        nnOut = pipeline.create(dai.node.XLinkOut)

        # Camera config
        camRgb.setPreviewKeepAspectRatio(False)
        camRgb.setFps(15)
        camRgb.setPreviewSize(416, 416)
        camRgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
        camRgb.setInterleaved(False)
        camRgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)

        # Image recognition config
        detectionNetwork.setConfidenceThreshold(0.5)
        detectionNetwork.setNumClasses(7)
        detectionNetwork.setCoordinateSize(4)
        detectionNetwork.setAnchors([
                10.0,
                13.0,
                16.0,
                30.0,
                33.0,
                23.0,
                30.0,
                61.0,
                62.0,
                45.0,
                59.0,
                119.0,
                116.0,
                90.0,
                156.0,
                198.0,
                373.0,
                326.0
        ])
        detectionNetwork.setAnchorMasks(
            {
                "side52": [0, 1, 2], 
                "side26": [3, 4, 5], 
                "side13": [6, 7, 8]
            }
        )
        detectionNetwork.setIouThreshold(0.5)
        detectionNetwork.setBlobPath(nnPath)
        detectionNetwork.setNumInferenceThreads(2) 
        detectionNetwork.input.setBlocking(False)

        # Name thy stream
        nnOut.setStreamName("nn")

        # Link to image recognition
        camRgb.preview.link(detectionNetwork.input)

        # Link to nnOut
        detectionNetwork.out.link(nnOut.input)

        # Video taping
        if isinstance(saveVideoPath, Path):
            try:
                if not saveVideoPath.exists():
                    saveVideoPath.touch()
                videoTape = saveVideoPath.open("w")

                rgbOut = pipeline.create(dai.node.XLinkOut)
                videoEnc = pipeline.create(dai.node.VideoEncoder)

                rgbOut.setStreamName("h265")
                videoEnc.setDefaultProfilePreset(30, dai.VideoEncoderProperties.Profile.H265_MAIN)

                camRgb.video.link(videoEnc.input)
                videoEnc.bitstream.link(rgbOut.input)
            except Exception as e:
                return Err(e)
        else:
            videoTape = None

        # Camera control
        controlIn = pipeline.create(dai.node.XLinkIn)
        controlIn.setStreamName("control")
        controlIn.out.link(camRgb.inputControl)

        try:
            _device = dai.Device(pipeline, usb2Mode=True)
            # This isn't a DeviceBase, as you seem to think!
            device: dai.Device = _device # type: ignore

            # Set camera settings
            qControl = device.getInputQueue(name="control")
            cc = dai.CameraControl()
            cc.setManualExposure(500, 200)
            if DEVELOPMENT_MODE == False:
                qControl.send(cc)

            # The queue should have the freshest data in it
            nnQueue = device.getOutputQueue(name="nn", maxSize=1, blocking=False)
            if videoTape is not None:
                rgbQueue = device.getOutputQueue(name="h265", maxSize=30, blocking=False)
                return Ok(Eye((videoTape, rgbQueue), nnQueue, device)) 
            else:
                return Ok(Eye(None, nnQueue, device)) 
        except Exception as e:
            return Err(e)

    def tick(self) -> Result[List[PixelDetection] | None, Exception]:
        """
        If successful, returns the latest detections, and attempts writing to video file.
        Returns None if no new data can be given.
        Returns BaseException on errors communicating with oak, or deserializing data.
        This method will not raise any exceptions.
        """

        try:
            _inDet = self.nnQueue.tryGet()
        except Exception as e:
            return Err(e)
        
        # Remove the generic
        inDet: None | dai.ImgDetections = _inDet # type: ignore

        if inDet is not None and inDet.detections is not None:
            results: List[PixelDetection] = []
            for detection in inDet.detections:
                padType = intoPadType(detection.label)
                if padType is None:
                    # Just skip it
                    continue

                    # return Err(Exception("A label on a detection was invalid. Label was " + str(detection.label)))
                
                # Find the center point
                centerX = (detection.xmin + detection.xmax) / 2
                centerY = (detection.ymin + detection.ymax) / 2
                
                results.append(PixelDetection(padType, PixelCoords(centerX, centerY), detection.confidence))
            return Ok(results)
        else:
            # No new data is available
            return Ok(None)
        
    def updateVideoTape(self) -> Result[None, Exception]:
        if self.videoTape is None:
            return Ok(None)
        (tapeFile, qRgb) = self.videoTape
        try:
            res = qRgb.tryGetAll()
            if res is not None:
                for frame in res:
                    data = frame.getData() # type: ignore
                    data.tofile(tapeFile) # type: ignore
            return Ok(None)
        except Exception as e:
            return Err(e)

