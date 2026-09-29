from pathlib import Path

import pytest

import inference


def test_parser_defaults():
    args = inference.build_parser().parse_args(["image.jpg"])

    assert args.image == Path("image.jpg")
    assert args.model == "yolo11n.pt"
    assert args.conf == pytest.approx(0.25)
    assert args.imgsz == 640
    assert args.device == "cpu"


def test_default_output_path():
    output = inference.default_output_path(Path("/tmp/frame.png"))
    assert output == Path("/tmp/frame_yolo.jpg")


def test_calculate_center_error_centered_box():
    cx, cy, ex, ey = inference.calculate_center_error(
        (270.0, 190.0, 370.0, 290.0),
        image_width=640,
        image_height=480,
    )

    assert cx == pytest.approx(320.0)
    assert cy == pytest.approx(240.0)
    assert ex == pytest.approx(0.0)
    assert ey == pytest.approx(0.0)


def test_calculate_center_error_offset_box():
    cx, cy, ex, ey = inference.calculate_center_error(
        (100.0, 100.0, 200.0, 200.0),
        image_width=640,
        image_height=480,
    )

    assert cx == pytest.approx(150.0)
    assert cy == pytest.approx(150.0)
    assert ex == pytest.approx(-170.0)
    assert ey == pytest.approx(-90.0)


def test_validate_confidence(tmp_path):
    image = tmp_path / "frame.jpg"
    image.write_bytes(b"not-an-image-but-file-exists")

    args = inference.build_parser().parse_args([str(image), "--conf", "1.5"])

    with pytest.raises(ValueError, match="--conf"):
        inference.validate_args(args)
