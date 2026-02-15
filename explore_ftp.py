import ftplib

def list_ftp_dirs(host, user, password):
    try:
        ftp = ftplib.FTP(host)
        ftp.login(user, password)
        print(f"Logged into {host}")
        
        print("\nRoot directory:")
        ftp.retrlines('LIST')
        
        # Check /now/ directory as suggested by search
        try:
            print("\nContents of /now/:")
            ftp.cwd('/now/')
            ftp.retrlines('LIST')
            
            # Check for hourly or daily folders
            subdirs = ftp.nlst()
            for sd in subdirs:
                if sd in ['half_hour_G', 'hourly', 'daily']:
                    print(f"\nChecking sub-directory: /now/{sd}/")
                    ftp.cwd(sd)
                    ftp.retrlines('LIST')
                    ftp.cwd('..')
        except Exception as e:
            print(f"Error accessing /now/: {e}")

        ftp.quit()
    except Exception as e:
        print(f"FTP Error: {e}")

if __name__ == "__main__":
    list_ftp_dirs("hokusai.eorc.jaxa.jp", "rainmap", "Niskur+1404")
