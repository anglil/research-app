import data_manager_sql as dm
print("Testing report generation...")
projects = dm.get_projects()
if projects:
    p = projects[0]
    report = dm.generate_project_report(p.id)
    print("Report Generated Successfully. Length:", len(report))
else:
    print("No projects to test.")
