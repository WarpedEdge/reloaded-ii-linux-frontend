`asi-bcj2.7z` is an original, non-executable regression fixture. Its member is named ASILoader64.dll solely to exercise the selection rule; it contains text and repeated synthetic branch bytes, not an upstream binary.

Uncompressed content:

```python
b"MZ - RLM regression fixture, not an executable\n" + b"\xe8\0\0\0\0\xe9\x01\0\0\0" * 100
```

Created using 7-Zip with `-m0=BCJ2 -m1=LZMA2 -m2=LZMA2 -m3=LZMA2 -mb0:1 -mb0s1:2 -mb0s2:3`.
