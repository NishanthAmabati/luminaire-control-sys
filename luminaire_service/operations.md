luminaire service is responsible for:
> accepting luminaire connections
> holding / maintaining the socket connections
> reading / sending data

methods:
get:
/devices: returns a list of all connected devices
/devices/luminaires: returns a list of connected luminaires
/devices/luminaire/{luminaire_ip}: returns info about a particular luminaire

post:
/devices/luminaires/{luminaire_ip}: accepts a new luminaire connection