# ============================================================
# TALQu3 Text to Speech Plugin for Whispering Tiger
# Version: 0.2.0
# This plug-in works with TALQu3.
# TALQuPRO is available from the developer Haruqa's
# FanBox or join HarupoLabo to get it.
# ============================================================

import io
import subprocess
import time
import Plugins
from os.path import abspath,isfile,join,exists
import os
import sys

import re
import json
import settings
import websocket
import audio_tools
import numpy as np
import yaml
import processmanager
import soundfile
class TALQu3PROTTSPlugin(Plugins.Base):
    TALQu3PRO_plugin_dir = join(os.getcwd() , "Plugins" , "TALQu3PRO_plugin")
    os.makedirs(TALQu3PRO_plugin_dir, exist_ok=True)
    wav_path = join(TALQu3PRO_plugin_dir,"TALQu3PRO.wav")
    log_path = join(TALQu3PRO_plugin_dir,"TALQu3PRO.log")
    for p in [log_path]:
        if not exists(p):
            with open(p, "w") as f:
                pass
    TALQu_path = ""
    action_flag = False
    data = {}
    target_sample_rate = 48000

    def init(self):


        self.init_plugin_settings(
            {
                "talqu_path": {"type": "file_open", "accept": ".exe", "value": ""},
                "play_mode":{"type": "select", "value": "", "values": ["onry","true","false"]},
                "speed":{"type": "slider", "min": 50, "max": 200, "step": 1, "value": 100},
                "inflection":{"type": "slider", "min": 0, "max": 2, "step": 0.001, "value": 1},
                "pitch_model":{"type": "slider", "min": 0.5, "max": 2, "step": 0.001, "value": 1},
                "small_pauses":{"type": "slider", "min": 10, "max": 800, "step": 1, "value": 400},
                "large_pauses":{"type": "slider", "min": 100, "max": 800, "step": 1, "value": 800},
                "pitch":{"type": "slider", "min": 0.5, "max": 2, "step": 0.01, "value": 1},
                "formant":{"type": "slider", "min": 0.5, "max": 2, "step": 0.001, "value": 1},
                "refine":{"type": "select", "value": "False", "values": ["True","False"]},
                "model_load_btn": {"label": "Load model", "type": "button", "style": "primary"},
                "split_string_num": {"type": "slider", "min": 0, "max": 30, "step": 1, "value": 10},
                "wait_time": {"type": "slider", "min": 0, "max": 20, "step": 1, "value": 5},
            },
            settings_groups={
                "General": ["talqu_path","play_mode","model_load_btn"],
                "Settings": ["speed", "inflection", "pitch_model", "small_pauses", "large_pauses", "pitch", "formant", "refine","split_string_num","wait_time"],
            }
        )
        self.TALQu_path = self.get_plugin_setting("talqu_path", "")

        if self.is_enabled(False):
            websocket.set_loading_state("talqu_plugin_loading", True)
            print(self.__class__.__name__ + " is enabled")
            settings.SetOption("tts_enabled", False)
            
            self.action_flag = self.check_version()
            print(self.action_flag)

            if not self.action_flag:
                print(self.__class__.__name__ + " is disabled and Non-supported version.")
                websocket.set_loading_state("talqu_plugin_loading", False)
                return
            self.load_model()
            websocket.set_loading_state("talqu_plugin_loading", False)
        else:
            print(self.__class__.__name__ + " is disabled")
            self.action_flag = False
            return
        pass

    def outLog(self,str):
        with open(self.log_path, 'a') as f:
        # ファイルにテキストを書き込む
            f.write(str+"\n")

    def check_version(self):
        command = self.TALQu_path +" getVersion"
        if self.TALQu_path is "":
            return False
        p = subprocess.Popen(command,stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
        try:
            out, err = p.communicate(timeout=30)
            self.outLog(out.decode('sjis'))
            if out.decode('sjis').split('.')[0] == "2":
                return True
        except subprocess.TimeoutExpired:
            p.terminate()
            p.wait()
        return False



    def load_model(self):
        command = self.TALQu_path +" getSpkName"
        self.outLog(command)
        p = subprocess.Popen(command,stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
        try:
            out, err = p.communicate(timeout=30)
            self.outLog(out.decode('sjis'))
            names = out.decode('sjis').split('\r\n')
            if len(names) >= 5:
                websocket.BroadcastMessage(json.dumps({
                    "type": "available_tts_voices",
                    "data": names[5].replace('TALQu3_Return:', '').split(',')
                }))
                self.outLog(names[5])
        except subprocess.TimeoutExpired:
            p.terminate()
            p.wait()

    def on_event_received(self, message, websocket_connection=None):
            if self.is_enabled(False):
                if "type" not in message:
                    return
                if message["type"] == "plugin_button_press":
                    if message["value"] == "model_load_btn":
                        self.load_model()

    def play_audio_on_device(self, wav, audio_device, source_sample_rate=24000, audio_device_channel_num=2, target_channels=2, is_mono=True, dtype="int16"):
        secondary_audio_device = None
        if settings.GetOption("tts_use_secondary_playback") and (
                (settings.GetOption("tts_secondary_playback_device") == -1 and audio_device != settings.GetOption("device_default_out_index")) or
                (settings.GetOption("tts_secondary_playback_device") > -1 and audio_device != settings.GetOption("tts_secondary_playback_device"))):
            secondary_audio_device = settings.GetOption("tts_secondary_playback_device")
            if secondary_audio_device == -1:
                secondary_audio_device = settings.GetOption("device_default_out_index")

        audio_tools.play_audio(wav, audio_device,
                                source_sample_rate=source_sample_rate,
                                audio_device_channel_num=audio_device_channel_num,
                                target_channels=target_channels,
                                is_mono=is_mono,
                                dtype=dtype,
                                secondary_device=secondary_audio_device, tag="tts")
    
    def predict(self, text):
        print(self.get_plugin_setting("play_mode", "false") == "false")
        data = [
        settings.GetOption("tts_voice"),
        ]
        if self.get_plugin_setting("play_mode", "false") == "false":
            data.append(self.wav_path)
        else:
            data.append("dummy")
        data.extend([
        text.replace(' ', '').replace(',', '、').replace('-', 'ー'),
        "",
        self.get_plugin_setting("play_mode", ""),
        self.get_plugin_setting("speed", 100),
        self.get_plugin_setting("inflection", 1),
        self.get_plugin_setting("pitch_model", 1),
        self.get_plugin_setting("small_pauses", 400),
        self.get_plugin_setting("large_pauses", 800),
        self.get_plugin_setting("pitch", 1),
        self.get_plugin_setting("formant", 1),
        self.get_plugin_setting("refine", False)
        ])
        return ",".join(map(str, data))

    def generate_tts(self,text):
        texts = []
        if settings.GetOption("tts_voice").startswith('TALQu2:'):
            n = int(self.get_plugin_setting("split_string_num", 10))
            texts.extend([text[i:i+n] for i in range(0, len(text), n)])
        else:
            texts.append(text)
        
        for t in texts:
            command = self.TALQu_path +" "+ self.predict(t)
            self.outLog(command)

            process_arguments = [self.TALQu_path, self.predict(t)]
            self.process = processmanager.run_process(process_arguments, env={})
            time.sleep(self.get_plugin_setting("wait_time", 5))
            print(self.process)
            if len(processmanager.all_processes) > 3:
                processmanager.cleanup_subprocesses()
    
    def stt(self, text, result_obj):
        if self.is_enabled(False) and settings.GetOption("tts_answer") and text.strip() != "" and self.action_flag:
            audio_device = settings.GetOption("device_out_index")
            if audio_device is None or audio_device == -1:
                audio_device = settings.GetOption("device_default_out_index")
            self.generate_tts(text.strip())
            if isfile(self.wav_path) and self.get_plugin_setting("play_mode", "false") == "false":
                wav_numpy = audio_tools.load_wav_to_bytes(self.wav_path, target_sample_rate=self.target_sample_rate)
                # Convert numpy array back to WAV bytes
                with io.BytesIO() as byte_io:
                    soundfile.write(byte_io, wav_numpy, samplerate=self.target_sample_rate,
                                    format='WAV')  # Explicitly specify format
                    wav_bytes = byte_io.getvalue()
                    self.play_audio_on_device(byte_io.getvalue(), audio_device,self.target_sample_rate)
        return

    def tts(self, text, device_index, websocket_connection=None, download=False):
        if self.is_enabled(False) and self.action_flag:
            audio_device = settings.GetOption("device_out_index")
            if audio_device is None or audio_device == -1:
                audio_device = settings.GetOption("device_default_out_index")
            self.generate_tts(text.strip())
            if isfile(self.wav_path) and self.get_plugin_setting("play_mode", "false") == "false":
                wav_numpy = audio_tools.load_wav_to_bytes(self.wav_path, target_sample_rate=self.target_sample_rate)
                # Convert numpy array back to WAV bytes
                with io.BytesIO() as byte_io:
                    soundfile.write(byte_io, wav_numpy, samplerate=self.target_sample_rate,
                                    format='WAV')  # Explicitly specify format
                    wav_bytes = byte_io.getvalue()
                    self.play_audio_on_device(byte_io.getvalue(), audio_device)
        return
    
    
    def timer(self):
        pass

    def on_enable(self):
        self.init()
        pass

    def on_disable(self):
        processmanager.cleanup_subprocesses()
        pass

