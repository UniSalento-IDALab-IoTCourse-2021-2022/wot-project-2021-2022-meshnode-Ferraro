const Bluez = require('bluez');
const bluetooth = new Bluez();

// Register callback for new devices
bluetooth.on('device', async (address, props) => {
    if(props.UUIDs[0] != undefined && props.UUIDs[0].includes("0000fdaa")){
        console.log("[NEW] Device:", address, props.RSSI);
       	const dev = await bluetooth.getDevice(address);
        dev.on("PropertiesChanged", (props) => {
           console.log("[CHG] Device:", address, props.RSSI);
    });
	 }

});


bluetooth.init().then(async () => {
    // listen on first bluetooth adapter
    const adapter = await bluetooth.getAdapter();
    await adapter.StartDiscovery();
    //console.log("Discovering");

    //after a while await adapter.StopDiscovery()
    
}).catch(console.error);


