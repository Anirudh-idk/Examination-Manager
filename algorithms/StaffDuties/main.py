import pandas as pd
import os

# Set Pandas to display all rows and columns
pd.set_option("display.max_rows", None)  # Show all rows
pd.set_option("display.max_columns", None)  # Show all columns


def get_room_data(staff_duties):
    try:
        room_data = pd.read_excel(staff_duties, sheet_name="ROOM")
    except:
        print("Error: Sheet 'ROOM' not found in the excel file")

    # Cleaning the data
    room_data[["Date", "Start Time", "End Time"]] = room_data["Time"].str.split(
        "|", expand=True
    )
    room_data = room_data.drop(columns=["Time"])
    room_data["Period"] = room_data["Start Time"].apply(
        lambda x: "AN" if x == "09:30" else "FN" if x == "14:00" else ""
    )
    room_data["Floor"] = room_data["Room"].apply(get_floor)

    return room_data


def get_staff_data(staff_duties):
    try:
        staff_data = pd.read_excel(staff_duties, sheet_name="STAFF", header=None)
    except:
        print("Error: Sheet 'STAFF' not found in the excel file")

    # Cleaning the data
    staff_data.columns = [
        "SNO",
        "ID",
        "Name",
        "Branch",
        "Role",
        "Mobile Number",
        "Email",
    ]

    return staff_data


def get_leave_data(staff_leave):
    leave_data = pd.read_excel(staff_leave)
    return leave_data


def get_floor(room_name):
    if room_name[-3:].isdigit():
        floor_number = int(room_name[-3])
        return "Ground Floor" if floor_number == 1 else "First Floor"
    return "Reserved"


def main_allot(room_data, staff_data, leave_data):

    # Merging Data (staff data and leave data)
    merged_data = pd.merge(
        staff_data,
        leave_data[["Name", "ID", "end_date"]],
        on=["ID", "Name"],
        how="left",
    )

    # Assinging Group captains and Room Captains
    room_captains = merged_data[merged_data["Role"] == "ROOM CAPTAIN"]
    group_captains = merged_data[merged_data["Role"] == "GROUP CAPTAIN"]

    # Indexing Room and Group Captains according to their branch

    room_data = room_data.sort_values(by=["Room", "Date", "Period"])
    room_data = room_data.drop_duplicates()

    # Allotment Logic

    room_data["Date"] = pd.to_datetime(room_data["Date"], format="%d-%m-%y")
    room_captains.loc[:, "end_date"] = pd.to_datetime(
        room_captains["end_date"], format="%d-%m-%y", errors="coerce"
    )
    group_captains.loc[:, "end_date"] = pd.to_datetime(
        group_captains["end_date"], format="%d-%m-%y", errors="coerce"
    )

    room_data = allot_room_captains(room_data, room_captains)
    room_data = allot_group_captains(room_data, group_captains)

    return room_data


# Allotment of room captains
def allot_room_captains(room_data, room_captains):
    room_data["Room Captain"] = None
    duties = {captain: [] for captain in room_captains["ID"]}
    branch_duty_count = {}

    for idx, row in room_data.iterrows():
        available_captains = room_captains[
            room_captains["end_date"].isna()
            | (room_captains["end_date"] != row["Date"])
        ]
        assigned_captains = []

        for _, captain_row in available_captains.iterrows():
            captain_id = captain_row["ID"]
            captain_name = captain_row["Name"]
            branch = captain_row["Branch"]

            # Initialize branch count for the date if not present
            if (row["Date"], branch) not in branch_duty_count:
                branch_duty_count[(row["Date"], branch)] = 0

            # Check branch constraint
            branch_total = len(room_captains[room_captains["Branch"] == branch])
            if (
                branch_duty_count[(row["Date"], branch)] < branch_total // 2
                and len(duties[captain_id]) < 10
                and not any(
                    duty_date == row["Date"] and duty_period != row["Period"]
                    for duty_date, duty_period in duties[captain_id]
                )
            ):

                assigned_captains.append(f"{captain_id} - {captain_name}")
                duties[captain_id].append((row["Date"], row["Period"]))
                branch_duty_count[(row["Date"], branch)] += 1

                if row["Room"] in ["F102", "F105"] and len(assigned_captains) < 2:
                    continue
                else:
                    break

        room_data.at[idx, "Room Captain"] = ", ".join(assigned_captains)

    # Convert date back to desired format for display
    room_data["Date"] = room_data["Date"].dt.strftime("%d-%m-%Y")

    return room_data


# Alloting Group Captains
def allot_group_captains(room_data, group_captains):
    room_data["Group Captain"] = None
    duties = {captain: [] for captain in group_captains["ID"]}
    branch_duty_count = {}

    for floor in room_data["Floor"].unique():
        floor_rooms = room_data[room_data["Floor"] == floor]

        for idx, row in floor_rooms.iterrows():
            available_captains = group_captains[
                group_captains["end_date"].isna()
                | (group_captains["end_date"] != row["Date"])
            ]

            for _, captain_row in available_captains.iterrows():
                captain_id = captain_row["ID"]
                captain_name = captain_row["Name"]
                branch = captain_row["Branch"]

                # Initialize branch count for the date if not present
                if (row["Date"], branch) not in branch_duty_count:
                    branch_duty_count[(row["Date"], branch)] = 0

                # Check branch constraint
                branch_total = len(group_captains[group_captains["Branch"] == branch])
                if (
                    branch_duty_count[(row["Date"], branch)] < branch_total // 2
                    and len(duties[captain_id]) < 10
                    and not any(
                        duty_date == row["Date"] and duty_period != row["Period"]
                        for duty_date, duty_period in duties[captain_id]
                    )
                ):

                    room_data.at[idx, "Group Captain"] = (
                        f"{captain_id} - {captain_name}"
                    )
                    duties[captain_id].append((row["Date"], row["Period"]))
                    branch_duty_count[(row["Date"], branch)] += 1
                    break

    return room_data


def export_csv(room_data):
    # Save the final results
    output_file_path = "Staff Duties.xlsx"

    if not os.path.exists(output_file_path):
        with pd.ExcelWriter(output_file_path, engine="openpyxl") as writer:
            room_data.to_excel(writer, sheet_name="FINAL", index=False)

    else:
        with pd.ExcelWriter(
            output_file_path, engine="openpyxl", mode="a", if_sheet_exists="replace"
        ) as writer:
            room_data.to_excel(writer, sheet_name="FINAL", index=False)

    print(f"Staff Duties exported to {output_file_path}")


def start_staff_duties_generation(staff_duties, staff_leave):
    print("Starting...")
    room_data = get_room_data(staff_duties)
    staff_data = get_staff_data(staff_duties)
    leave_data = get_leave_data(staff_leave)
    room_data = main_allot(room_data, staff_data, leave_data)
    export_csv(room_data)
