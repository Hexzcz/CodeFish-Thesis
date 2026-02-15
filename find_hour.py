import ftplib
import os
import gzip
import numpy as np

def find_specific_hour():
    host, user, password = "hokusai.eorc.jaxa.jp", "rainmap", "Niskur+1404"
    ftp = ftplib.FTP(host)
    ftp.login(user, password)
    
    path = "/now/half_hour_G/2026/02/04/"
    ftp.cwd(path)
    files = sorted([f for f in ftp.nlst() if f.endswith('.gz')])
    print(f"Checking {len(files)} files for Feb 4...")

    for f_name in files:
        # Check every 2 hours to save time
        hour = f_name.split('.')[2][:2]
        if int(hour) % 2 != 0: continue
            
        local = "hour_test.gz"
        with open(local, 'wb') as f_obj:
            ftp.retrbinary(f"RETR {f_name}", f_obj.write)
        
        with gzip.open(local, 'rb') as f_obj:
            data = np.frombuffer(f_obj.read(), dtype='<f4').reshape(1200, 3600)
            def lat_to_idx(lat): return int((60.0 - lat) / 0.1)
            def lon_to_idx(lon): return int(lon / 0.1)
            
            # Quezon City Bounding Box
            l1, l2 = lat_to_idx(14.8), lat_to_idx(14.6)
            o1, o2 = lon_to_idx(121.0), lon_to_idx(121.2)
            qc_max = np.max(data[l1:l2, o1:o2])
            
            if qc_max > 0:
                print(f"HOUR {hour}:00 has QC Rain: {qc_max} mm/h")
            else:
                # Check wider Luzon
                l1, l2 = lat_to_idx(18), lat_to_idx(12)
                o1, o2 = lon_to_idx(120), lon_to_idx(123)
                luzon_max = np.max(data[l1:l2, o1:o2])
                print(f"HOUR {hour}:00 - QC: 0, Luzon Max: {luzon_max} mm/h")
        
        os.remove(local)
    ftp.quit()

if __name__ == "__main__":
    find_specific_hour()
