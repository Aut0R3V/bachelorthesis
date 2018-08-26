#!/usr/bin/env python

import h5py
import signal
import argparse
import numpy as np
from os import path
from environment import VrepEnvironment
import parameters as param

# Configure Command Line interface
controller = dict(tf="target following controller", oa="obstacle avoidance controller")
parser = argparse.ArgumentParser(description='Evaluate the controller')
parser.add_argument('controller', choices=controller, default='oa', help="tf - target following, oa - obstacle avoidance")
parser.add_argument('dir', help='Base directory of the experiment eg. ./data/session_xyz', default=param.default_dir)
args = parser.parse_args()

# Import after argparse is done to prevent nest from showing up in help
from model import Model


# Stop the Simulation and save results up to that point
def signal_handler(signal, frame):
	global stop_signal_received
	stop_signal_received = True

stop_signal_received = False
signal.signal(signal.SIGINT, signal_handler)

print "Using", controller[args.controller]
is_oa = args.controller == controller['oa']

model = Model()

# Read network weights
h5f = h5py.File(path.join(args.dir, param.weights_file), 'r')
w_l = np.array(h5f['w_l'], dtype=float)
w_r = np.array(h5f['w_r'], dtype=float)
model.snn_tf.set_weights(w_l, w_r)
if is_oa:
	w_p = np.array(h5f['w_p'], dtype=float)
	model.snn_oa.set_weights(w_p[0], w_p[1])
h5f.close()

if is_oa:
	env = VrepEnvironment(param.plus_path, param.plus_path_mirrored)
else:
	env = VrepEnvironment(param.evaluation_path, param.evaluation_path_mirrored)

# Arrays of variables that will be saved
reward = []
angle_to_target = []
episode_steps = []
episode_completed = []

# Initialize environment, get state, get reward
s, r = env.reset()

for i in range(param.evaluation_length):

	# Simulate network for 50 ms
	angle = model.simulate(s)

	# Feed output spikes into snake model
	# Get state, angle to target, reward, termination, step, path completed
	s, a, r, t, n, p = env.step(angle)

	# Store information that should be saved
	if t:
		episode_steps.append(n)
		episode_completed.append(p)
	reward.append(r)
	angle_to_target.append(a)

	# Print progress
	if i % (param.evaluation_length / 100) == 0:
		print "Evaluation progress ", (i / (param.evaluation_length / 100)), "%"

	if stop_signal_received:
		break

# Save performance data
h5f = h5py.File(path.join(args.dir, param.evaluation_file), 'w')
h5f.create_dataset('angle_to_target', data=angle_to_target)
h5f.create_dataset('reward', data=reward)
h5f.create_dataset('episode_steps', data=episode_steps)
h5f.create_dataset('episode_completed', data=episode_completed)
h5f.close()
