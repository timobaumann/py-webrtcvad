import collections
import contextlib
import sys
import wave

import webrtcvad


def read_wave(path):
    with contextlib.closing(wave.open(path, 'rb')) as wf:
        num_channels = wf.getnchannels()
        assert num_channels == 1
        sample_width = wf.getsampwidth()
        assert sample_width == 2
        sample_rate = wf.getframerate()
        assert sample_rate in (8000, 16000, 32000)
        duration = wf.getnframes() / sample_rate
        pcm_data = wf.readframes(wf.getnframes())
        return pcm_data, sample_rate, duration


class Frame(object):
    def __init__(self, bytes, timestamp, duration):
        self.bytes = bytes
        self.timestamp = timestamp
        self.duration = duration


def frame_generator(frame_duration_ms, audio, sample_rate):
    n = int(sample_rate * (frame_duration_ms / 1000.0) * 2)
    offset = 0
    timestamp = 0.0
    duration = (float(n) / sample_rate) / 2.0
    while offset + n < len(audio):
        yield Frame(audio[offset:offset + n], timestamp, duration)
        timestamp += duration
        offset += n


def vad_collector(sample_rate, frame_duration_ms,
                  padding_duration_ms, vad, frames):
    num_padding_frames = int(padding_duration_ms / frame_duration_ms)
    ring_buffer = collections.deque(maxlen=num_padding_frames)
    triggered = False
    voiced_frames = []
    start = 0
    end = 0
    for frame in frames:
        if not triggered:
            ring_buffer.append(frame)
            num_voiced = len([f for f in ring_buffer
                              if vad.is_speech(f.bytes, sample_rate)])
            if num_voiced > 0.9 * ring_buffer.maxlen:
                #sys.stdout.write('+(%s)' % (ring_buffer[0].timestamp,))
                start = ring_buffer[0].timestamp
                triggered = True
                voiced_frames.extend(ring_buffer)
                ring_buffer.clear()
        else:
            voiced_frames.append(frame)
            ring_buffer.append(frame)
            num_unvoiced = len([f for f in ring_buffer
                                if not vad.is_speech(f.bytes, sample_rate)])
            if num_unvoiced > 0.9 * ring_buffer.maxlen:
                #sys.stdout.write('-(%s)\n' % (frame.timestamp + frame.duration))
                triggered = False
                end = frame.timestamp + frame.duration
                yield (start, end)
                #yield b''.join([f.bytes for f in voiced_frames])
                ring_buffer.clear()
                voiced_frames = []
    # deal with speech at the end of file:
    if triggered:
        #sys.stdout.write('-(%s)' % (frame.timestamp + frame.duration))
        end = frame.timestamp + frame.duration
    #sys.stdout.write('\n')
    if voiced_frames:
        #yield b''.join([f.bytes for f in voiced_frames])
        yield (start, end)


def main(args):
    if len(args) < 2:
        sys.stderr.write(
            'Usage: example.py <aggressiveness> <path to wav file>\n')
        sys.exit(1)
    aggressiveness = int(args[0])
    totalVoiced = 0
    totalDuration = 0
    for filename in args[1:]:
        audio, sample_rate, duration = read_wave(filename)
        voiced = 0
        vad = webrtcvad.Vad(aggressiveness)
        frames = frame_generator(30, audio, sample_rate)
        #frames = list(frames)
        segments = vad_collector(sample_rate, 30, 300, vad, frames)
        for i, (start, end) in enumerate(segments):
            voiced += end - start
        print("duration:\t%s\tvoiced:\t%s\tprop:%s\tfile\t%s" % (duration, voiced, voiced/duration, filename))
        totalDuration += duration
        totalVoiced += voiced
    if len(args) > 2:
        print("total duration:\t%s\ttotal voiced:\t%s\ttotal prop:%s" % (totalDuration, totalVoiced, totalVoiced/totalDuration))


if __name__ == '__main__':
    main(sys.argv[1:])
