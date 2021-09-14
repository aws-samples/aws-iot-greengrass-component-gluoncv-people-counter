# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this
# software and associated documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights to use, copy, modify,
# merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import argparse
from gluoncv import model_zoo, data, utils
import json
import matplotlib.pyplot as plt
import mxnet as mx
from mxnet import image
import numpy as np
import os
from PIL import Image
import time

import IPCUtils as ipcutil
# from labels import labels
from awscrt.io import (
    ClientBootstrap,
    DefaultHostResolver,
    EventLoopGroup,
    SocketDomain,
    SocketOptions,
)
from awsiot.eventstreamrpc import Connection, LifecycleHandler, MessageAmendment
from awsiot.greengrasscoreipc.model import PublishToIoTCoreRequest
import awsiot.greengrasscoreipc.client as client

# remote debug harness -- uncomment to use
# import ptvsd
# import socket
# this_ip = (([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")] or [[(s.connect(("8.8.8.8", 53)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) + ["no IP found"])[0]
# ptvsd.enable_attach(address=(this_ip,3000), redirect_output=True)
# ptvsd.wait_for_attach()
# end debug harness

plt.ioff()

# Read in command-line parameters
parser = argparse.ArgumentParser()
parser.add_argument("-c", "--class", action="store", required=False, dest="class_name", default="person", help="class name to collection from predictions")
parser.add_argument("-m", "--model", action="store", required=False, dest="model", default="ssd_512_resnet50_v1_voc", help="model name from gluon zoo")
parser.add_argument("-r", "--rate", action="store", required=False, dest="rate", default="0.5", help="max frames per second to predict")
parser.add_argument("-s", "--source", action="store", required=False, dest="source", default="/tmp/data/frame.jpg", help="source file to read")
parser.add_argument("-t", "--topic", action="store", required=False, dest="topic", default="demo/topic", help="topic to report predictions")
parser.add_argument("-z", "--threshold", action="store", required=False, dest="threshold", default="0.75", help="confidence threshold")
parser.add_argument("-o", "--output", action="store", required=False,  dest="output_pattern", default='/tmp/output', help="output file -- e.g. /tmp/output%04d.jpg")
parser.add_argument("-n", "--num_outputs", action="store", required=False, dest="num_outputs", default=1000, help="max number of output files")
# set globals from args
args = parser.parse_args()
topic = args.topic
source_file = args.source
model_name = args.model
max_frame_rate = float(args.rate)
class_name = args.class_name
threshold = float(args.threshold)
output_pattern = args.output_pattern
num_outputs = args.num_outputs

print(f"using {json.dumps(args.__dict__)}")

def print_msg_to_stdout(msg, topic=topic, qos=0):
    print(msg)

def publish_to_iot_core(msg, topic=topic, qos=0):
    print_msg_to_stdout(msg)
    ipc_client.new_publish_to_iot_core().activate(
               request=PublishToIoTCoreRequest(topic_name=topic, qos=qos,
                                            payload=msg.encode()))

# debug mock injection
send_message = publish_to_iot_core
if os.getenv("AWS_GG_NUCLEUS_DOMAIN_SOCKET_FILEPATH_FOR_COMPONENT") == None:
    send_message = print_msg_to_stdout
else:
    print("loading the IPC Client")
    ipc_utils = ipcutil.IPCUtils()
    connection = ipc_utils.connect()
    ipc_client = client.GreengrassCoreIPCClient(connection)
    print("loaded")


# load model
ctx = mx.cpu()
net = model_zoo.get_model(model_name, pretrained=True, ctx=ctx)


def capture_file(src_file, timeout=1):
    start = time.time()

    # wait for timeout, then check for source file availability
    while True:
        time.sleep(1/max_frame_rate)
        if os.path.exists(src_file):
            break
        if time.time() > start + timeout:
            raise Exception(f"source {src_file} doesn't exist within timeout") 

    # capture the source file by renaming to a new file. Using ms as suffix to file to minimize any collisions
    ms_count = int((time.time() %1)*1000)
    path_parts = list(os.path.split(src_file))
    file_parts = path_parts[-1].split('.')

    file_parts[-2] += str(ms_count)
    path_parts[-1] = ".".join(file_parts)

    new_file = os.path.join(*path_parts)
    # rename is atomic, so if this call succeeds, you can use the new file
    os.rename(src_file, new_file)

    return new_file


def predict(filename, network):
    x, img = data.transforms.presets.ssd.load_test(filename, short=512)
    class_IDs, scores, bounding_boxes = net(x)

    return class_IDs, scores, bounding_boxes


def get_object_boxes(network, class_ids, scores, bounding_boxes, object_label, threshold=threshold):
    good_scores = (scores[0,:,0] > threshold)
    good_classes = (class_ids[0,:,0] == network.classes.index(object_label))

    boxes = bounding_boxes[0,:,:].asnumpy()[(good_scores.asnumpy()*good_classes.asnumpy()) > 0]

    return boxes


output_count = 0
def get_output_file():
    global output_count
    global output_pattern
    global num_outputs

    filename = output_pattern
    try:
        filename = filename % output_count
    except:
        pass
    finally:
        output_count = output_count + 1
        if output_count >= num_outputs:
            output_count = 0

    return filename


def overlay_boxes(filename, bounding_boxes, scores, threshold=threshold, outfile='test.jpg'):
    x, img = data.transforms.presets.ssd.load_test(filename, short=512)
    plt.ioff()
    fig = plt.gcf()
    ax = utils.viz.plot_bbox(img, bounding_boxes[0], scores[0],
                        #class_IDs[0], #class_names,
                        thresh=threshold)
    plt.axis('off')
    plt.savefig(outfile)


def make_message(label, boxes, frame_rate, outfile=None):
    d = { "Label": label,
          "Count": len(boxes),
          "Bounding_Boxes": boxes,
          "Frame_Rate": frame_rate
        }

    return json.dumps(d)


start = time.time()
frame_cnt = 0
filename = ""
while True:
    try:
        filename = capture_file(source_file)      
        class_IDs, scores, bounding_boxes = predict(filename, net)

        boxes = get_object_boxes(net, class_IDs, scores, bounding_boxes,class_name)
        frame_cnt += 1
        frame_rate = frame_cnt/(time.time() - start)

        # draw bounding boxes for objects above threshold
        outfile = get_output_file()
        if outfile is not None:
            overlay_boxes(filename, bounding_boxes, scores, threshold, outfile)

        send_message(make_message(class_name, boxes.tolist(), frame_rate, outfile))
        
    except Exception as e:
        print(e)

    finally: 
        try:
            os.remove(filename)
        except Exception as e:
            pass

try:
    os.remove(filename)
except Exception as e:
    pass
