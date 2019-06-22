# rr-camera
Robot Ronny camera

## Install
```
git clone https://github.com/robot-ronny/rr-camera.git

cd rr-camera

sudo pip3 install -e .
```

## Service enable
```
pm2 --interpreter "python3" start rr-camera

pm2 save
```

## Usage
```
rr-camera --help
```

## MQTT

If object detected or lost

ronny/camera/object-detected  bool

If object move

ronny/camera/object {"x": int, "y": int, "dx": int, "dy": int, "radius": int}
