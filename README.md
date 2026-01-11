# electroapp-ha-addon

doplnek elektroapp do ha

build by 

nezapomen upravit verzi!

docker buildx build --platform linux/amd64,linux/arm64/v8 -t mondychan/elektroapp-ha:0.1.3 -t mondychan/elektroapp-ha:latest -f dockerfile --push .

buildni, pak pridej do HA
nastavit

musis si vytvorit influxdb usera a vlozit jeho credintials do nastaveni

