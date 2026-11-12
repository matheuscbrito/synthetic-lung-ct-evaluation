import numpy as np
import pytest

from frameworks.noise_evaluator import masked_nps as m


def test_recovers_known_frequency_in_a_mask_without_full_32_pixel_square():
    y, x = np.indices((128, 128))
    mask = (y % 32) < 12
    field = np.sin(2 * np.pi * x * .1875)
    drift = .07 * x - .03 * y
    real = np.where(mask, field + drift, -1e8)
    synthetic = np.where(mask, 2 * field + drift, 1e8)

    sums = m.masked_sums(mask, real, synthetic)
    freq, profiles = m.radial_profiles(sums.products, sums.pairs)

    assert np.array_equal(sums.used, mask)
    assert freq[np.argmax(profiles[0])] == pytest.approx(.1875, abs=1 / m.NFFT)
    np.testing.assert_allclose(profiles[1], 4 * profiles[0], atol=1e-12)
    assert m.readings(freq, profiles[1]).sigma == pytest.approx(2 * m.readings(freq, profiles[0]).sigma)


def test_empty_mask_cannot_be_read_as_zero_noise():
    image = np.ones((64, 64))
    sums = m.masked_sums(np.zeros_like(image, dtype=bool), image)
    with pytest.raises(ValueError, match="too little soft tissue"):
        m.radial_profiles(sums.products, sums.pairs)
