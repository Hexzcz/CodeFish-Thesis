import ftplib
import os
import gzip
import numpy as np

def check_kristine():
    host, user, password = "hokusai.eorc.jaxa.jp", "rainmap", "Niskur+1404"
    ftp = ftplib.FTP(host)
    ftp.login(user, password)
    
    # Typhoon Kristine peaked around Oct 22-24, 2024
    days = ['22', '23', '24']
    
    # QC Bounding Box
    def lat_idx(lat): return int((60.0 - lat) / 0.1)
    def lon_idx(lon): return int(lon / 0.1)
    l1, l2 = lat_idx(14.8), lat_idx(14.6)
    o1, o2 = lon_idx(121.0), lon_idx(121.2)

    for day in days:
        path = f"/now/half_hour_G/2024/10/{day}/"
        try:
            ftp.cwd(path)
            files = sorted([f for f in ftp.nlst() if f.endswith('.gz')])
            # Check 4 times for that day
            for f_name in files[::6]:
                local = "kristine.gz"
                with open(local, 'wb') as fo: ftp.retrbinary(f"RETR {f_name}", fo)
                with gzip.open(local, 'rb') as fo:
                    data = np.frombuffer(fo.read(), dtype='<f4').reshape(1200, 3600)
                    qc_max = np.max(data[l1:l2, o1:o2])
                    hour = f_name.split('.')[2][:2]
                    print(f"DEBUG: 2024-10-{day} Hour {hour}:00 - QC Max Intensity: {qc_max:.2f} mm/h")
                    if qc_max > 5.0:
                        print(f"!!! FOUND HEAVY RAIN IN QC !!! Date: 2024-10-{day} Hour: {hour}:00 UTC")
                        ftp.quit()
                        return
                os.remove(local)
        except: continue
    ftp.quit()

if __name__ == "__main__":
    check_kristine()
