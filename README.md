# Localisation and telemetry under Bluetooth Mesh

The code in this repository is part of a bigger project for the Internet of Things course at the University of Salento

The aim of the project is to verify the possibility of sending telemetry information and locating objects at the same time by using a Bluetooth Mesh network.

What done has been developed and tested using several Raspberry Pi computers.

## The system

The system is made up of three main components:

- Nodes. Those are the devices created for the actual location and their code is in this repository.

- Server. This element contains a node that collects data from the other ones. The code for the server component is reachable [here](https://github.com/UniSalento-IDALab-IoTCourse-2021-2022/wot-project-2021-2022-server-Ferraro). After data are collected, relative positions are computed by using RSSI and log-distance path loss model. Both location and telemetry data are sent to a dashboard after being managed.

- Dashboard. This is what the final user sees. It shows a grid map with red squares corresponding to the positions of the nodes that are part of the system. Once a telemetry message arrives, the square of the node that sent it becomes orange. Once a device is tracked, its position is computed through the three-border method and shown with a yellow square. [Here](https://github.com/UniSalento-IDALab-IoTCourse-2021-2022/wot-project-2021-2022-dashboard-Ferraro) the code.

## The Node

This repository contains the implementation of the single node of the system. The python scripts use the bluez API to connect to the Mesh.

2 types of node have been created. One is only able to retrieve and send over the network information about the RSSI computed by scanning the environment and looking for an Eddystone-UID beacon. The second type has the same capabilities but includes another element with a model that simulates data from a temperature sensor and sends them.

`index.js` is the application that scans the environment looking for the beacon. It saves the result of the scan to a file.

`node.py` is the python script that manages the connection with the Bluetooth mesh for a regular node. It reads from the file of the previous step and sends the data after formatting them.

`node_prov.py` is necessary for the very first configuration of the node device. It manages the provisioning procedure and creates the actual node (that will be used by `node.py`) on the device. Remember that for the provisioning procedure, an external device is needed.

`telemetry_node.py` is the script that manages the node with a sensor.

`telemetry_node_prov.py` does for a telemetry node the same things that `node_prov.py` does for the simpler node.

After provisioning the device, please substitute in the right file (either `node.py` or `telemetry_node.py`) the value of the `token` variable in the main entry with the one assigned to the node by the provisioner.

`nodo.sh` is a startup script used to manage the different phases (scanning and sending).

NOTE: a node cannot use both `node.py` and `telemetry_node.py`

After provisioning the nodes, in order for the system to work, is necessary to copy the folder:

`/var/lib/Bluetooth/mesh/<your-node-id>`

in the same folder `nodo.sh` is, and change the path in the very first lines of the same file with the right one for your device. The aim of this procedure is to save configuration data in a known place and copy them each time back to their right position. This is necessary because configuration files sometimes disappear from their position without a clear motivation.

It may be helpful to fully delete the `rpl` subfolder from the configuration files discussed before in order to avoid bugs during the communication with the server.