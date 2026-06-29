"""superesp.framework.audio — compact MFCC features for KWS / sound heads.

A small, dependency-light MFCC (numpy + scipy.fftpack.dct) that turns a 1-D
waveform into a fixed-length feature vector of n_mfcc * n_frames values
(<= MAX_SEQ), which the FeatureTokenizer then quantizes to bytes. This is the
same front-end an ESP32 firmware would run on I2S-mic frames.
"""
from __future__ import annotations

import numpy as np
from scipy.fftpack import dct


def _mel(f):       return 2595.0 * np.log10(1.0 + f / 700.0)
def _mel_inv(m):   return 700.0 * (10.0 ** (m / 2595.0) - 1.0)


def _mel_filterbank(n_filters: int, n_fft: int, sr: int) -> np.ndarray:
    low, high = _mel(0), _mel(sr / 2)
    pts = _mel_inv(np.linspace(low, high, n_filters + 2))
    bins = np.floor((n_fft + 1) * pts / sr).astype(int)
    fb = np.zeros((n_filters, n_fft // 2 + 1))
    for i in range(1, n_filters + 1):
        l, c, r = bins[i - 1], bins[i], bins[i + 1]
        for k in range(l, c):
            if c > l: fb[i - 1, k] = (k - l) / (c - l)
        for k in range(c, r):
            if r > c: fb[i - 1, k] = (r - k) / (r - c)
    return fb


def mfcc_features(
    wave: np.ndarray, sr: int = 16000, *,
    n_mfcc: int = 10, n_frames: int = 3, n_filters: int = 26,
    frame_len: int = 400, n_fft: int = 512,
) -> np.ndarray:
    """Return a flattened (n_mfcc * n_frames,) MFCC feature vector.

    The waveform is split into n_frames equal segments; each segment's MFCC
    (mean over its sub-windows) gives n_mfcc coeffs. Total = n_mfcc*n_frames.
    """
    wave = np.asarray(wave, dtype=np.float64)
    if wave.size == 0:
        return np.zeros(n_mfcc * n_frames)
    # normalize
    m = np.max(np.abs(wave))
    if m > 0:
        wave = wave / m
    fb = _mel_filterbank(n_filters, n_fft, sr)
    ham = np.hamming(frame_len)
    seg_len = len(wave) // n_frames if len(wave) >= n_frames else len(wave)
    hop = max(frame_len // 2, 1)
    feats = []
    for fi in range(n_frames):
        seg = wave[fi * seg_len : (fi + 1) * seg_len] if seg_len else wave
        if len(seg) < frame_len:
            seg = np.pad(seg, (0, frame_len - len(seg)))
        # Average log-mel over ALL sliding windows spanning this segment, so the
        # whole segment is represented (not just its first 25 ms).
        acc = np.zeros(n_filters)
        n_win = 0
        for s in range(0, len(seg) - frame_len + 1, hop):
            win = seg[s : s + frame_len] * ham
            spec = np.abs(np.fft.rfft(win, n=n_fft)) ** 2
            acc += np.log(np.maximum(fb @ spec, 1e-10))
            n_win += 1
        if n_win == 0:  # segment shorter than one window
            win = np.pad(seg, (0, max(0, frame_len - len(seg))))[:frame_len] * ham
            spec = np.abs(np.fft.rfft(win, n=n_fft)) ** 2
            acc = np.log(np.maximum(fb @ spec, 1e-10))
            n_win = 1
        coeffs = dct(acc / n_win, type=2, norm="ortho")[:n_mfcc]
        feats.append(coeffs)
    return np.concatenate(feats)  # (n_mfcc * n_frames,)
