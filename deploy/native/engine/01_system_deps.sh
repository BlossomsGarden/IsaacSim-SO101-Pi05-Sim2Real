#!/bin/bash
set -eu
export DEBIAN_FRONTEND=noninteractive
date -Is
apt-get update
apt-get install -y --no-install-recommends libvulkan1 vulkan-tools libegl1 libgl1 libglu1-mesa libx11-6 libxcursor1 libxrandr2 libxi6 libxinerama1 libxkbcommon0 libxkbcommon-x11-0 libsm6 libxt6 libxrender1 libgomp1 libnss3 libasound2
vulkaninfo --summary > /root/autodl-tmp/isaac/logs/vulkan-summary.txt 2>&1
vulkaninfo > /root/autodl-tmp/isaac/logs/vulkan-full.txt 2>&1
grep -E 'deviceName|deviceType|driverVersion|apiVersion|VK_KHR_acceleration_structure|VK_KHR_ray_tracing_pipeline' /root/autodl-tmp/isaac/logs/vulkan-full.txt
date -Is
