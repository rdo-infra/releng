import os
import pandas
import review_utils

releases = ["centos8-ussuri", "centos8-victoria", "centos8-wallaby",
            "centos8-master", "centos8-xena", "centos8-yoga", "centos9-yoga",
            "centos9-master"]
general_ftbfs_report = "/tmp/general_ftbfs_report"


def get_ftbfs_failures(release, output_file):
    """
    This function is parsing csv report to look for any occurenence
    of FTBFS and store this information
    """
    url = "https://trunk.rdoproject.org/%s/status_report.csv" % release
    print("INFO: Analysing report from URL: ", url)

    df_data = pandas.read_csv(url, index_col='Project')
    df_data.drop(["Extended Sha", "Packages"], axis=1, inplace=True)
    failed_reviews = df_data[df_data["Status"] == "FAILED"]
    if not failed_reviews.empty:
        for project in failed_reviews.index:
            failed_reviews = failed_reviews.assign(Release=release)
        if os.stat(output_file).st_size == 0:
            failed_reviews.to_csv(output_file, mode='a',
                                  sep=',', index=True)
        else:
            failed_reviews.to_csv(output_file, mode='a', sep=',',
                                  header=None, index=True)
        print(failed_reviews)
        return failed_reviews
    else:
        print("No package build failures found in ", release)
        print("")


def modify_report():

    report = pandas.read_csv(general_ftbfs_report, index_col='Project')

    report["Review"] = None
    report["Logs"] = None
    # TODO: enable source commit hash
    # report["Commit"] = None
    report["Date of FTBFS"] = None

    for project in report.index:
        rpmbuild_log = "https://trunk.rdoproject.org/" \
                       + report["Release"][project] + "/component/" \
                       + report['Component'][project] + "/" \
                       + report['Source Sha'][project][:2] + "/" \
                       + report['Source Sha'][project][2:4] + "/" \
                       + report['Source Sha'][project] + "_" \
                       + report['Dist Sha'][project][:8] + "/rpmbuild.log"

        report.loc[project, "Logs"] = rpmbuild_log
        report.loc[project, "Date of FTBFS"] = pandas.to_datetime(report
                                               ['Timestamp'][project],
                                               unit='s')
        report.loc[project, "Review"] = list_current_ftbfs_reviews(project
                                        .split("-")[1], report["Release"]
                                        [project].split("-")[1], "open")

    report.drop(["Timestamp", "Source Sha", "Dist Sha"], axis=1, inplace=True)
    report.to_csv(general_ftbfs_report, mode='w', sep=',', index=True)
    print(report)


def list_current_ftbfs_reviews(project, branch, status):
    """
    This function is calling gerrit API to list all current
    FTBFS reviews, with specified project, branch and status.
    """
    client = review_utils.get_gerrit_client('rdo')
    gerrit_url = 'https://review.rdoproject.org/r/#/c/'

    if branch and "master" in branch:
        branch = "rpm-master"
    elif branch:
        branch = branch + "-rdo"

    reviews = review_utils.get_reviews_project(client, project,
                                               branch=branch,
                                               status=status,
                                               intopic="FTBFS")
    if reviews:
        latest_review = 0
        for review in reviews[::-1]:
            if latest_review < review['_number']:
                latest_review = review['_number']

        return gerrit_url + str(latest_review)


open(general_ftbfs_report, "w").close()
for release in releases:
    get_ftbfs_failures(release, general_ftbfs_report)


modify_report()
