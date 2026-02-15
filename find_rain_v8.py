import ftplib
import os
import gzip
import numpy as np

def find_rain_v8():
    host, user, password = "hokusai.eorc.jaxa.jp", "rainmap", "Niskur+1404"
    ftp = ftplib.FTP(host)
    ftp.login(user, password)
    
    # Let's try September 2024 (Typhoon Yagi/Enteng month)
    path = "/standard/v8/hourly/2024/09/"
    
    def lat_idx(lat): return int((60.0 - lat) / 0.1)
    def lon_idx(lon): return int(lon / 0.1)
    l1, l2 = lat_idx(14.8), lat_idx(14.6)
    o1, o2 = lon_idx(121.0), lon_idx(121.2)

    try:
        ftp.cwd(path)
        days = sorted(ftp.nlst(), reverse=True)
        for d in days[:10]:
            ftp.cwd(d)
            files = [f for f in ftp.nlst() if f.endswith('.gz')]
            if files:
                f_name = files[len(files)//2]
                local = "v8.gz"
                with open(local, 'wb') as fo: ftp.retrbinary(f"RETR {f_name}", fo)
                with gzip.open(local, 'rb') as fo:
                    data = np.frombuffer(fo.read(), dtype='<f4').reshape(1200, 3600)
                    qc_max = np.max(data[l1:l2, o1:o2])
                    if qc_max > 1.0:
                        hour = f_name.split('.')[2][:2]
                        print(f"!!! SUCCESS !!! Date: 2024-09-{d} Hour: {hour}:00, Intensity: {qc_max:.2f} mm/h")
                        ftp.quit()
                        return
                os.remove(local)
            ftp.cwd("..")
    except: pass
    ftp.quit()

if __name__ == "__main__":
    find_rain_v8()
