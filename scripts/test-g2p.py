from gloss2pose import PoseLookup, scale_down, prepare_glosses
from pose_format.pose_visualizer import PoseVisualizer
import cv2
import numpy as np
from time import time
import base64

lookup = PoseLookup(directory="../data/gloss2pose", language="asl")
glosses = prepare_glosses("wrong")
# print(glosses) 
pose, words = lookup.gloss_to_pose(glosses)
# print(pose, words)
scale_down(pose, 512)
p = PoseVisualizer(pose, thickness=2)
img = p.save_png(None, p.draw(transparency=True))
img_base64 = base64.b64encode(img).decode('utf-8')
start = time()
print({"img": img_base64, "words": words, "time-taken": time() - start})
b64_string = img_base64  

decoded_bytes = base64.b64decode(b64_string)
with open("pose.png", "wb") as f:
    f.write(decoded_bytes)

print("✅ Saved pose.png")
