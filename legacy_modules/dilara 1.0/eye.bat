@echo off
color a
title the eye
cls
:a
echo.
echo.
echo welcome to the eye
echo place of begin everything
echo.
echo.
echo.
echo 2.nasa
echo 3.china
echo 4.usa
echo 5.russia
echo 6.isverc
echo 7.hollanda
echo 8.italya
echo 9.almanya 
set /p choice=
if %choice%==1 goto ping
if %choice%==2 goto scan
if %choice%==3 goto tree
if %choice%==4 goto help
if %choice%==5 goto systeminfo
if %choice%==6 goto starter
if %choice%==7 goto tracert
if %choice%==8 goto b
if %choice%==9 goto lsd
goto a
:tracert
start http://loeffingencam.selfhost.eu/view/view.shtml?id=174&imagepath=%2Fmjpg%2F1%2Fvideo.mjpg&size=1
start http://80.94.55.92/view/index.shtml
goto A
goto a
:starter
start http://wc-heli.chuv.ch/view/view.shtml
start http://webcam-1.faxa.rvk.is/view/index.shtml
start http://lv.raad.tartu.ee:10201/view/index.shtml
start http://200.36.58.250/view/view.shtml?id=62&imagepath=%2Fmjpg%2F1%2Fvideo.mjpg&size=1
start http://195.196.36.242/view/index.shtml
start http://71.248.101.58:50001/CgiStart?page=Single&Language=0
start http://195.196.35.91/view/view.shtml?id=565&imagePath=%2Fmjpg%2Fvideo.mjpg&size=1
goto A
goto a
:help
@echo off
cls
echo college
echo sec
echo hol
echo other
set /p choice=
if %choice%==college goto sc
if %choice%==sec goto start 
if %choice%==hol goto systemerror
if %choice%==other goto flash
goto a
:sc
start http://janet.ing.unibs.it/
start http://rifwebcam.chem.psu.edu/
start http://cyclops.sunderland.ac.uk/view/index.shtml
start http://trackfield.webcam.oregonstate.edu/axis-cgi/mjpg/video.cgi?resolution=800x600&amp%3Bdummy=1333689998337
start http://128.196.12.29/axis-cgi/mjpg/video.cgi
start http://buscam.uchicago.edu/view/index.shtml
start http://mbewebcam.rhul.ac.uk/view/view.shtml?imagePath=/mjpg/video.mjpg&size=2
start http://webcam01.ecn.purdue.edu/view/index.shtml
start http://flightcam2.pr.erau.edu/view/view.shtml?id=3801&imagepath=%2Fmjpg%2Fvideo.mjpg&size=1
goto A
goto a
:flash
start http://129.15.81.9:8080/webcam.html
start http://208.65.20.83/axis-cgi/mjpg/video.cgi?resolution=4cif&dummy=1344350498922 
start http://193.90.139.222:33450/axis-cgi/mjpg/video.cgi?resolution=800x450
start http://62.168.0.189/axis-cgi/mjpg/video.cgi?resolution=4CIF&camera=1&dummy=1277833957855
start http://64.122.208.241:8000/axis-cgi/mjpg/video.cgi?camera=&resolution=320x240
start http://storatorg.halmstad.se/axis-cgi/mjpg/video.cgi?resolution=1280x800&dummy=1433493481969
start http://82.139.167.140:3131/view/index.shtml
start http://avptcam.uconn.edu/view/index.shtml
start http://webcam.thealgonquin.com:8080/view/index.shtml
start http://200.79.225.81:8080/view/view.shtml?id=608&imagePath=%2Fmjpg%2Fvideo.mjpg&size=1
goto A
goto a
:B
start http://camera.hcc.govt.nz/view/view.shtml
start http://roccabella.asuscomm.com:9091/view/view.shtml?id=577&imagePath=/mjpg/video.mjpg&size=8&camera=1
start http://webcam.st-malo.com/axis-cgi/mjpg/video.cgi?resolution=352x288
start http://83.61.22.4:8080/view/viewer_index.shtml?id=0
start http://ppcam.gotdns.com:8000/axis-cgi/mjpg/video.cgi?resolution=2CIFEXP&dummy=1344349278882 
start http://89.162.72.203/axis-cgi/mjpg/video.cgi?resolution=CIF&dummy=1306400814056
start http://195.235.198.107:3344/view/index.shtml
start http://cam-cityhall1.delft.nl/view/view.shtml?id=782&imagepath=%2Fmjpg%2Fvideo.mjpg&size=1
goto A
goto a
:lsd
start http://217.22.201.135/view/viewer_index.shtml?id=17222
start http://webcam.ampere.inpg.fr/view/index.shtml
start http://87.54.59.228/view/viewer_index.shtml?id=193
start http://217.30.178.109:46744/view/index.shtml
start http://217.78.137.43/view/index.shtml
start http://cam.hintertuxerhof.at/view/index.shtml
start http://webcam.eins-energie.de/view/index.shtml
start http://217.22.201.135/view/viewer_index.shtml?id=17222
start http://87.54.59.228/view/viewer_index.shtml?id=193
start http://217.30.178.109:46744/view/index.shtml
start http://tornet.no-ip.org/view/index.shtml
start http://94.125.79.44/view/index.shtml
start http://livecam.norran.se/view/viewer_index.shtml?id=34342
goto A
goto a
:start 
start http://115.42.155.199/view/indexFrame.shtml
start http://flightcam2.pr.erau.edu/view/index.shtml
start http://camera6.buffalotrace.com/view/index.shtml
start http://87.54.59.228/view/index.shtml
start http://202.208.150.120/ViewerFrame?Mode=Motion&Language=1 
start http://74.94.148.163:8080/ViewerFrame?Mode=Motion 
start http://116.193.97.222/CgiStart?page=Single&Language=1 
start http://24.240.181.138:8181/ViewerFrame?Mode=Motion&Resolution=640x480&Quality=Motion&Interval=30&Size=STD&PresetOperation=Move&Language=0
start http://webcam.geodan.nl/
start http://193.140.1.239:8080/xmlui/
start http://205.167.90.185/view/viewer_index.shtml?id=4680
start http://cam4.uridium.ch/CgiStart?page=Single&Mode=Motion&Resolution=320x240&Quality=Motion&Interval=30&Size=STD&PresetOperation=Move&Language=0
goto A
goto a
:systemerror
start http://hadynbuild.cf.ac.uk/view/index.shtml 
start http://137.44.28.240/view/index.shtml
start http://camera.buffalotrace.com/view/viewer_index.shtml?id=221430 
start http://218.219.195.243:8080/MultiCameraFrame?Mode=Motion&Language=0
start http://193.138.213.169/CgiStart?page=Single&Mode=Motion&Language=9
start http://pendelcam.kip.uni-heidelberg.de/view/viewer_index.shtml?id=170059
start http://iut-info.univ-reims.fr/view/
start http://webcam.geodan.nl/
start http://flightcam2.pr.erau.edu/view/index.shtml 
start http://67.53.162.163/index4.html
start http://200.36.58.250/view/index.shtml 
start http://217.7.66.54/axis-cgi/mjpg/video.cgi?resolution=640x360&dummy=1423492017252
start http://200.36.58.250/view/index.shtml 

goto A
:end
end 
goto A
goto a
:scan
start http://tarotchilivisit2.oamp.fr
start http://150.214.222.100/view/view.shtml?id=1070&imagepath=%2Fmjpg%2Fvideo.mjpg&size=1
start http://www.runningmars.kuk.net/multimedia/webcams/view3.html
start http://sidecam.obspm.fr/view/viewer_index.shtml?id=3826
start http://tarot4.obs-azur.fr/view/view.shtml?id=6241&imagePath=/mjpg/video.mjpg&size=1
goto A
goto a
:tree
start http://59.146.77.13/CgiStart?page=Single&Language=1
start http://113.161.194.216:86/CgiStart?page=Single&Mode=Refresh&Interval=3&Language=0
start http://61.60.112.230/view/view.shtml?imagePath=/mjpg/2/video.mjpg&size=1
start http://nav.ddo.jp:82/ViewerFrame?Mode=Motion&Language=0
goto A
goto a
:ping 
goto A
goto a
:systeminfo
start http://92.50.128.90/axis-cgi/mjpg/video.swf?resolution=640x480&compression=30&dummy=1275773919735
start http://212.42.54.137:8008/view/index.shtml
start http://195.113.207.238/view/index.shtml  
start http://www.vladimir-city.ru:8080/view/index.shtml 
start http://myndavel.ma.is/view/index.shtml
start http://webcam.st-malo.com/axis-cgi/mjpg/video.cgi?resolution=352x288
start http://ppcam.gotdns.com:8000/axis-cgi/mjpg/video.cgi?resolution=2CIFEXP&dummy=1344349278882 
start http://89.162.72.203/axis-cgi/mjpg/video.cgi?resolution=CIF&dummy=1306400814056
start http://195.235.198.107:3344/view/index.shtml
start http://80.38.183.149:2000/view/index.shtml
start http://camera.butovo.com/view/index.shtml
start http://cam-cityhall1.delft.nl/view/view.shtml?id=782&imagepath=%2Fmjpg%2Fvideo.mjpg&size=1
start http://213.196.182.244/view/index.shtml
start http://195.74.79.83:30/view/index.shtml
goto A
