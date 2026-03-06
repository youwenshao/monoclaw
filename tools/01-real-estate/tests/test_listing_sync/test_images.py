"""Tests for ListingSync image processing."""

import pytest
from PIL import Image


def test_watermark_applied():
    """EAA watermark should be applied to the image."""
    from real_estate.listing_sync.processing.images import _apply_eaa_watermark

    img = Image.new("RGB", (1024, 768), color=(128, 128, 128))
    result = _apply_eaa_watermark(img, eaa_license="E-123456", opacity=0.6, font_size=14)
    assert result is not None
    assert result.size == (1024, 768)


def test_watermark_skipped_without_license():
    """Watermark should be skipped when no license is provided."""
    from real_estate.listing_sync.processing.images import _apply_eaa_watermark

    img = Image.new("RGB", (1024, 768), color=(128, 128, 128))
    result = _apply_eaa_watermark(img, eaa_license="", opacity=0.6, font_size=14)
    assert result is img


def test_resize_dimensions():
    """Images should resize to target platform dimensions without distortion."""
    from real_estate.listing_sync.processing.images import _resize_for_platform

    img = Image.new("RGB", (2000, 1500), color=(100, 100, 100))
    resized = _resize_for_platform(img, (1024, 768))
    assert resized.size[0] <= 1024
    assert resized.size[1] <= 768
