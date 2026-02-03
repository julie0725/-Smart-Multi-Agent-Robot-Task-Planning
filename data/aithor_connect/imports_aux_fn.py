import math
import re
import shutil
import subprocess
import time
import threading
import cv2
import numpy as np
from ai2thor.controller import Controller
from scipy.spatial import distance
from typing import Tuple
from collections import deque
import random
import os
from glob import glob

def closest_node(node, nodes, no_robot, clost_node_location):
    crps = []
    distances = distance.cdist([node], nodes)[0]
    dist_indices = np.argsort(np.array(distances))
    for i in range(no_robot):
        pos_index = dist_indices[(i * 5) + clost_node_location[i]]
        crps.append (nodes[pos_index])
    return crps

def distance_pts(p1: Tuple[float, float, float], p2: Tuple[float, float, float]):
    return ((p1[0] - p2[0]) ** 2 + (p1[2] - p2[2]) ** 2) ** 0.5

def generate_video():
    frame_rate = 5
    cur_path = os.path.dirname(__file__) + "/*/"
    
    # ffmpeg 설치 확인
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("   ffmpeg가 설치되지 않았습니다. 비디오를 생성하지 않습니다.")
        print("   설치: sudo apt install ffmpeg -y")
        return
    
    print("\n🎬 비디오 생성 중...")
    for imgs_folder in glob(cur_path, recursive=False):
        view = imgs_folder.split('/')[-2]
        if not os.path.isdir(imgs_folder):
            print("The input path: {} you specified does not exist.".format(imgs_folder))
        else:
            command_set = ['ffmpeg', '-y', '-i',  # -y: 덮어쓰기 자동 허용
                          '{}/img_%05d.png'.format(imgs_folder), 
                          '-framerate', str(frame_rate),
                          '-pix_fmt', 'yuv420p',
                          '{}/video_{}.mp4'.format(os.path.dirname(__file__), view)]
            
            try:
                # ffmpeg 출력 숨김 (깔끔한 터미널)
                subprocess.call(command_set, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print(f"video_{view}.mp4 생성 완료")
            except Exception as e:
                print(f"video_{view}.mp4 생성 실패: {e}")
    print("비디오 생성 완료\n")


