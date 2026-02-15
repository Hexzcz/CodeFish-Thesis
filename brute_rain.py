import ftplib
import os
import gzip
import numpy as np

def brute_force_rain():
    host, user, password = "hokusai.eorc.jaxa.jp", "rainmap", "Niskur+1404"
    ftp = ftplib.FTP(host)
    ftp.login(user, password)
    
    # Try November 2024 (Very active Typhoon month: Marce, Nika, Ofel, Pepito)
    path = "/now/half_hour_G/2024/11/"
    
    def lat_idx(lat): return int((60.0 - lat) / 0.1)
    def lon_idx(lon): return int(lon / 0.1)
    l1, l2 = lat_idx(14.8), lat_idx(14.6)
    o1, o2 = lon_idx(121.0), lon_idx(121.2)

    try:
        ftp.cwd(path)
        days = sorted(ftp.nlst(), reverse=True)
        for d in days:
            ftp.cwd(d)
            files = [f for f in ftp.nlst() if f.endswith('.gz')]
            if files:
                # Check Noon and Midnight
                for f_name in [files[0], files[len(files)//2]]:
                    local = "brute.gz"
                    with open(local, 'wb') as fo: ftp.retrbinary(f"RETR {f_name}", fo)
                    with gzip.open(local, 'rb') as fo:
                        fd = fo.read()
                        if len(fd) < 17280000: continue # Basic size check
                        data = np.frombuffer(fd, dtype='<f4').reshape(1200, 3600)
                        qc_max = np.max(data[l1:l2, o1:o2])
                        if qc_max > 0.5:
                            hour = f_name.split('.')[2][:2]
                            print(f"!!! FOUND !!! Date: 2024-11-{d} Hour: {hour}:00, Intensity: {qc_max:.2f} mm/h")
                            ftp.quit()
                            return
                    os.remove(local)
            ftp.cwd("..")
            print(f"Checked day {d}... no heavy QC rain.")
    except Exception as e:
        print(f"Error: {e}")
    ftp.quit()

if __name__ == "__main__":
    brute_force_rain()
