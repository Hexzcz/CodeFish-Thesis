import ftplib

def list_october():
    host, user, password = "hokusai.eorc.jaxa.jp", "rainmap", "Niskur+1404"
    ftp = ftplib.FTP(host)
    ftp.login(user, password)
    
    # Based on the earlier explore results, Oct 2024 exists
    path = "/now/half_hour_G/2024/10/"
    try:
        ftp.cwd(path)
        days = sorted(ftp.nlst())
        print(f"Days in Oct 2024: {days}")
    except Exception as e:
        print(f"Error: {e}")
    ftp.quit()

if __name__ == "__main__":
    list_october()
