# Enrollment Audio Samples

Put original registration audio samples here.

Example:

```text
data/enroll/
  zhangsan/
    sample_001.wav
    sample_002.wav
  lisi/
    sample_001.wav
```

These `.wav` files are not the final voiceprint database. They are source samples.

Run this command to convert them into the final speaker database:

```powershell
saidao-audio enroll --input data\enroll --output data\speakers.json
```

The generated `data\speakers.json` is the voiceprint database used by live recognition.
