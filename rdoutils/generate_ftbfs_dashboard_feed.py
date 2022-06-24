import csv
import pandas
import subprocess

# TODO
# craft log links
# connect information from gerrit review list
# with report info and append it to general repo

releases=["centos8-xena", "centos8-yoga", "centos8-master", "centos9-yoga", "centos9-master"]
general_ftbfs_report = "/tmp/general_ftbfs_report"

def get_ftbfs_failures(release, output_file):
    """
    This function is parsing csv report to look for any occurenence
    of FTBFS and store this information
    """
    url = "https://trunk.rdoproject.org/%s/status_report.csv" % release
    print("INFO: Analysing report from URL: ", url)

    data=pandas.read_csv(url)
    df_data=pandas.DataFrame(data)

    failed_reviews = df_data[df_data["Status"] == "FAILED" ]
    if len(failed_reviews.index) > 1:
        failed_reviews.to_csv(output_file, mode='a', sep=',', index=False)
        print("INFO: Found current package builiding failures:")
        print(failed_reviews)


def list_current_ftbfs_reviews():
    ftbfs_reviews = subprocess.getoutput('ftbfs_rdo -s open -p "*"')
    print("INFO: Current FTBFS reviews opened:")
    print(ftbfs_reviews)


open(general_ftbfs_report, "w").close()

for release in releases:
    get_ftbfs_failures(release, general_ftbfs_report)
list_current_ftbfs_reviews()
