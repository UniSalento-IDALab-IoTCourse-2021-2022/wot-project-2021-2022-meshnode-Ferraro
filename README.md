# Localisation and telemetry under Bluetooth Mesh

The code in this repository is part of a bigger project for the Internet of Things course at the University of Salento

The aim of the project is to verify the possibility of sending telemetry information and locating objects at the same time by using a Bluetooth Mesh network.

What done has been developed and tested using several Raspberry Pi computers.

## The system

The system is made up of three main components:

- Nodes. There are two types of nodes: nodes with a sensor and nodes without it. Both types scan the environment for the signal of an Eddystone-UID beacon and send what is found over the Mesh network. The nodes with a sensor are able to send the value they read from it too. [Here](https://github.com/UniSalento-IDALab-IoTCourse-2021-2022/wot-project-2021-2022-meshnode-Ferraro) the code for this component of the system

- Server. This component of the system is the one contained in this repository.

- Dashboard. This is what the final user sees. It shows a grid map with red squares corresponding to the positions of the nodes that are part of the system. Once a telemetry message arrives, the square of the node that sent it becomes orange. Once a device is tracked, its position is computed through the three-border method and shown with a yellow square. [Here](https://github.com/UniSalento-IDALab-IoTCourse-2021-2022/wot-project-2021-2022-dashboard-Ferraro) the code.

## The Server

The server of the system described is in this repository.

Both location and telemetry data are collected from the nodes by the `server.py` script. It connects with the node on the device and manages the messages.

`server_prov.py` is responsible for the provisioning procedure. After that a node will be created on the device, ready to be used by `server.py`. Remember that for the provisioning procedure, an external device is needed. After the provisioning procedure, the token assigned by the provisioner has to be assigned as a value to the variable `token` in the `main` entry of `server.py`.

`wsServer.js` is a Node.js application containing a WebSocket server. Data collected by `server.py` are stored in two text files. Once a new client connects to the server, it starts observing those files, formatting the data, and sending them to the Dashboard. During this procedure, the log-distance path loss model is used for computing a distance measure in meters starting from the RSSI value provided by the nodes.