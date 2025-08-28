from django.urls import path

from . import views

app_name = "sao"
urlpatterns = [
    path("", views.home, name="home"),
    path(
        "del_office_hours/<office_hours>/",
        views.del_office_hours,
        name="del_office_hours",
    ),
    path(
        "modify_record/<int:record_id>/<int:year>/<int:month>/",
        views.modify_record,
        name="modify_record",
    ),
    path("overview/", views.overview, name="overview"),

    # 雇用者管理
    path("employee/", views.employee_list, name="employee_list"),
    path("employee/add", views.add_employee, name="add_employee"),
    path("employee/<int:employee_no>/edit", views.edit_employee, name="edit_employee"),
    path("leave/<int:pk>", views.leave_from_company, name="leave_from_company"),

    path("employee_record/", views.employee_record, name="employee_record"),
    path(
        "staff_detail/<employee>/<int:year>/<int:month>/",
        views.staff_detail,
        name="staff_detail",
    ),
    path("time_clock/", views.time_clock, name="time_clock"),
    path("permission/", views.permission, name="permission"),
    path(
        "modify_permission/<int:user_id>/",
        views.modify_permission,
        name="modify_permission",
    ),
    path("holiday_settings/", views.holiday_settings, name="holiday_settings"),
    path(
        "office_hours_list/<int:employee_no>",
        views.office_hours_list,
        name="office_hours_list",
    ),
    path(
        "progress/<int:pk>/", views.progress, name="progress"
    ),  # 進捗が表示されていくペー
    path("update_annual_leave", views.update_annual_leave, name="update_annual_leave"),
    path(
        "download_csv/<int:employee_no>/<int:year>/<int:month>",
        views.download_csv,
        name="download_csv",
    ),
    path(
        "webtimestamp/<int:employee_no>/",
        views.web_timestamp_view,
        name="web_timestamp_view",
    ),
    path(
        "add_steppingout/<int:record>/<int:year>/<int:month>",
        views.add_steppingout,
        name="add_steppingout",
    ),
    path(
        "modify_steppingout/<int:steppingout>/<int:record>/<int:year>/<int:month>",
        views.modify_steppingout,
        name="modify_steppingout",
    ),
    path(
        "dep_steppingout/<int:steppingout>/<int:record>/<int:year>/<int:month>",
        views.del_steppingout,
        name="del_steppingout",
    ),
    path("change_stamp_id", views.change_stamp_id, name="change_stamp_id"),
    path("get_employee_json", views.get_employee_json, name="get_employee_json"),
    path("fix_holiday", views.fix_holiday, name="fix_holiday"),
    path("req_test/", views.req_test),
    path("working_hours/", views.working_hours_view, name="working_hours_view"),
    path("working_hours/add", views.add_working_hours, name="add_working_hours"),
    path("working_hours/<int:id>/delete/", views.del_working_hours, name="del_working_hours"),
    path("working_hours/<int:id>/update/", views.update_working_hours, name="edit_working_hours"),
]
