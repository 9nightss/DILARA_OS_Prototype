@echo off
color a
title cyberstorm
echo.
echo dark future is on the net
:a
cls
echo 1.kaspersky
echo 2.nasa
echo 3.china
echo 4.usa
echo 5.russia
echo 6.microsoft
echo 7.encom 
echo 8.CTAN,
echo 9.debian
echo.
set /p choice=
if %choice%==1 goto ping
if %choice%==2 goto scan
if %choice%==3 goto tree
if %choice%==4 goto help
if %choice%==5 goto systeminfo
if %choice%==6 goto starter
if %choice%==7 goto tracert
if %choice%==8 goto lds
if %choice%==9 goto deb
goto a
:deb
start ftp debian.org
start 
goto a
:lds
echo !warming!
echo here is just 69 sites and all connect same system...
echo !REMEMBER!
pause 
start ftp ctan.epst-tlemcen.dz
start ftp ftp.leg.uct.ac.za
start ftp ftp.sun.ac.za
start ftp ctan.mirror.ac.za
start ftp mirrors.ustc.edu.cn
start ftp ftp.jaist.ac.jp
start ftp ftp.kddilabs.jp
start ftp ftp.u-aizu.ac.jp 
start ftp ftp.kaist.ac.kr
start ftp ftp.ktug.org
start ftp ftp.neowiz.com
start ftp mirror.pregi.net
start ftp latex.imamu.edu.sa
start ftp ftp.ccu.edu.tw
start ftp ftp.yzu.edu.tw
start ftp mirror.aut.ac.nz
start ftp mirror.easyname.at
start ftp mirror.datacenter.by
start ftp mirrors.dotsrc.org
start ftp ftp.funet.fi
start ftp distrib-coffee.ipsl.jussieu.fr
start ftp ftp.oleane.net
start ftp mirrors.ircam.fr
start ftp ftp.fau.de
start ftp ftp.fernuni-hagen.de
start ftp ftp.fu-berlin.de
start ftp ftp.gwdg.de
start ftp ftp.mpi-sb.mpg.de
start ftp ftp.rrze.uni-erlangen.de
start ftp ftp.rrzn.uni-hannover.de
start ftp ftp.tu-chemnitz.de
start ftp mirror.physik-pool.tu-berlin.de
start ftp sunsite.informatik.rwth-aachen.de
start ftp ftp.cc.uoc.gr
start ftp ftp.ntua.gr
start ftp ftp.heanet.ie
start ftp ctan.uib.no 
start ftp ftp.gust.org.pl
start ftp ftp.piotrkosoft.net
start ftp sunsite.icm.edu.pl
start ftp ftp.di.uminho.pt
start ftp ftp.eq.uc.pt
start ftp ftp.ist.utl.pt
start ftp mirrors.fe.up.pt
start ftp mirror.macomnet.net
start ftp ftp.acc.umu.se
start ftp mirror.switch.ch
start ftp ftp.cvut.cz
start ftp mirrors.nic.cz
start ftp archive.cs.uu.nl
start ftp ctan.triasinformatica.nl
start ftp ftp.snt.utwente.nl
start ftp anorien.csc.warwick.ac.uk
start ftp mirror.ox.ac.uk
start ftp ctan.math.ca
start ftp ctan.mirror.rafal.ca
start ftp mirror.its.dal.ca
start ftp ftp.muug.ca
start ftp mirrors.ucr.ac.cr
start ftp tug.ctan.org
start ftp ctan.sharelatex.com
start ftp ftp.math.purdue.edu
start ftp mirror.jmu.edu
start ftp mirrors.rit.edu
start ftp mirror.utexas.edu
start ftp ftp.lasca.ic.unicamp.br
start ftp linorg.usp.br
start ftp ctan.dcc.uchile.cl
start ftp ftp.inf.utfsm.cl
start ftp ftp.dante.de
goto a
:ping
start ftp ftp.kaspersky.ru
goto A
goto a
:tracert
start ftp encomwireless.com
start ftp encomkb.encom.com.au
start ftp encomsystems.com
start ftp encom.info
goto A
goto a
:starter
start ftp ftp.microsoft.com
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
goto a
:sc
start ftp ftp.cs.toronto.edu
start ftp ftp.prism.oregonstate.edu
start ftp edinformatics.com
goto A
goto a
:start 
start ftp mgrs-data.org
start ftp ftp.cert.org
start ftp ftp.ripe.net
start ftp ftp.dante.de
start ftp ftp.leg.uct.ac.za
start ftp ftp.zebra.org
goto A
goto a
:systemerror
start ftp netcorptrailers.com
start ftp vipmart.com
start ftp ftp.symantec.com
start ftp mindfully.org
start ftp ftp.fedex.com
start ftp phase5.a1k.org
goto A
goto a
:end
end 
goto A
goto a
:scan
start ftp 137.78.232.95
start ftp 198.122.199.232
start ftp ssd.jpl.nasa.gov
start telnet horizons.jpl.nasa.gov 6775
start ftp naif.jpl.nasa.gov
goto A
goto a
:tree
start ftp bnk.de
start ftp ftp.democracynow.org
start ftp ftp.cuhk.edu.hk
start ftp ftp.u-aizu.ac.jp
goto A
goto a
:ping 
start ftp ftp.settlers3.com
start ftp ftp.ubi.com
goto A
goto a
:systeminfo
start ftp ftp.kaspersky.ru
start ftp ftp.hikvision.ru
start ftp ftp.ru.debian.org
start ftp ftp.dns-shop.ru
start ftp ftp.spbexchange.ru
start ftp ftp.ctm.ru
start ftp ftp.dlink.ru
start ftp ftp.solveigmm.com
start ftp ftp.iana.org
goto A