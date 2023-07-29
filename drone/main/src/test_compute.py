import compute
from compute import LocationDetection
from optics import PixelCoords
from dronekit import LocationGlobal
from optics import PadType

def test_relativeDistance():
    assert compute.relativeDistance(100, PixelCoords(0.5, 0.5), 0) == (0.0, 0.0)
    
    result = compute.relativeDistance(69, PixelCoords(0.95, 0.12), 360)
    assert result[0] > 0 and result[1] > 0

    result = compute.relativeDistance(13, PixelCoords(0.4, 0.6), -360)
    assert result[0] < 0 and result[1] < 0

    assert compute.relativeDistance(0, PixelCoords(69.0, 420.0), 720) == (0.0, 0.0)
    
    # Yaw testing
    assert compute.relativeDistance(28, PixelCoords(0.5, 1.0), 90)[1] == 0.0 

    result = compute.relativeDistance(71, PixelCoords(0.5, 0.5), 0)
    result2 = compute.relativeDistance(71, PixelCoords(0.5, 0.5), 90)
    assert result2 == (result[0], -result[1])

def test_conductor():
    mock = compute.Conductor()
    mock.add_detections([
        LocationDetection(PadType.smoresDropoff, LocationGlobal(20, -30, 0), 0.2),
        LocationDetection(PadType.smoresDropoff, LocationGlobal(20, -30, 0), 0.3),

        LocationDetection(PadType.smoresDropoff, LocationGlobal(21, -31, 0), 0.9),

        LocationDetection(PadType.medkitDropoff, LocationGlobal(20, -30, 0), 0.6)
    ])
    mock.add_detections([
        LocationDetection(PadType.smoresDropoff, LocationGlobal(20, -30, 0), 0.1)
    ])

    assert len(mock.detections) == 3
    assert mock.get_best_guess(PadType.smoresDropoff).confidence == 0.9
    assert mock.get_best_guess(PadType.medkitDropoff).confidence == 0.6