__author__ = "TUM-Doepfert"
__credits__ = "jiahechu"
__license__ = ""
__maintainer__ = "TUM-Doepfert"
__email__ = "markus.doepfert@tum.de"

import os

import numpy as np
import pandas as pd
from ruamel.yaml.compat import ordereddict

import hamlet.constants as c
from hamlet.creator.agents.agent_base import AgentBase
import hamlet.functions as f


class Producer(AgentBase):
    """
        Sets up producer agents. Inherits from Agents class.

        Mainly used for excel file creation. Afterwards Sfh class creates the individual agents.
    """

    def __init__(self, input_path: str, config: ordereddict, config_path: str, scenario_path: str, config_root: str):

        # Call the init method of the parent class
        super().__init__(input_path, config, config_path, scenario_path, config_root)

        # Define agent type
        self.type = c.A_PRODUCER

        # Path of the input file
        self.input_path = os.path.join(input_path, 'agents', self.type)

        # Number of agents
        self.num_agents = 0  # number of agents (changes depending on which "add_xxx()" function is called)

        # Index list that is adhered to throughout the creation process to ensure correct order
        self.idx_list = None  # gets created in create_general()
        self.idx_start = 0  # start index where to insert values (changes based on dataframe length)
        self.idx_end = 0

        # Misc
        self.n_digits = 3  # number of digits values get rounded to in respective value column

    def create_df_from_config(self) -> pd.DataFrame:
        """
            Function to create the dataframe that makes the Excel sheet
        """

        # Set the method
        self.method = 'config'

        # Create the overall dataframe structure for the worksheet
        self.create_df_structure()

        # Fill the pv information in dataframe
        self.add_pv()

        # Fill the wind information in dataframe
        self.add_wind()

        # Fill the fixed generation information in dataframe
        self.add_fixed_gen()

        return self.df

    def create_df_from_grid(self, grid: dict, fill_from_config: bool = False, **kwargs) -> pd.DataFrame:

        # Load the grid information
        self.grid = grid

        # Load the bus sheet
        self.bus = self.grid['bus']

        # Get the rows in the load sheet of the agent type
        self.load = self.grid['load'][self.grid['load']['agent_type'] == self.type]

        # The agents are all the buses that have an inflexible load
        self.agents = self.load[self.load['load_type'] == c.P_INFLEXIBLE_LOAD]

        # Get the rows in the sgen sheet that the owners in the owners column match with the index in the load sheet
        self.sgen = self.grid['sgen'][self.grid['sgen']['owner'].isin(self.load.index)]

        # Get the number of agents and set the method
        self.num = self.get_num_from_grid(self.grid['load'], self.type)
        self.method = 'grid'

        # Create the overall dataframe structure for the worksheet
        self.create_df_structure()

        # Note: As the grid file does not include producer type agents this cannot be done yet
        return self.df

        # Fill the general information in dataframe
        self.fill_general()

        # Fill the pv information in dataframe
        self.fill_pv(**kwargs)

        # Fill the wind information in dataframe
        self.fill_wind(**kwargs)

        # Fill the fixed generation information in dataframe
        self.fill_fixed_gen(**kwargs)

        # Fill the battery information in dataframe
        self.fill_battery(**kwargs)

        # Fill the model predictive controller information in dataframe
        self.fill_ems()

        return self.df

    def create_df_structure(self):
        """
            Function to create the dataframe structure with the respective columns
        """
        # Go through file and create the columns for the ctss worksheet
        columns = ordereddict()
        before = True  # variable to insert entries before the plants
        max_bat = 1  # variable to keep track of how many batteries need to be added
        for key, _ in self.config.items():
            cols = self.make_list_from_nested_dict(self.config[key])

            # Define and insert all columns that come before the plants
            if before:
                befkeys = ["general"]
                for befkey in befkeys:
                    befcols = [col for col in cols if befkey in col]
                    # Adjust the columns from "general"
                    if befkey == "general":
                        befcols[0] = f"{befkey}/agent_id"
                        befcols.insert(1, f"{befkey}/name")
                        befcols.insert(2, f"{befkey}/comment")
                        befcols.insert(3, f"{befkey}/bus")
                    columns[befkey] = befcols

                # Set before to False as it only runs once
                before = False

            # Adjust the columns from "pv"
            if key == c.P_PV:
                self.num += self.config[key]["general"]["number_of"]
                # Filter all columns that match the key
                cols = [col for col in cols if key in col]
                del cols[3]
                del cols[1]
                cols.insert(0, f"{key}/owner")
                max_num = max(self.config[key][key]["num"])
                cols = cols[:2] + self.repeat_columns(columns=cols[2:7], num=max_num) + cols[7:]
            # Adjust the columns from "wind"
            elif key == c.P_WIND:
                self.num += self.config[key]["general"]["number_of"]
                # Filter all columns that match the key
                cols = [col for col in cols if key in col]
                del cols[3]
                del cols[1]
                cols.insert(0, f"{key}/owner")
                max_num = max(self.config[key][key]["num"])
                cols = cols[:2] + self.repeat_columns(columns=cols[2:5], num=max_num) + cols[5:]
            # Adjust the columns from "fixed_gen"
            elif key == c.P_FIXED_GEN:
                self.num += self.config[key]["general"]["number_of"]
                # Filter all columns that match the key
                cols = [col for col in cols if key in col]
                del cols[3]
                del cols[1]
                cols.insert(0, f"{key}/owner")
                max_num = max(self.config[key][key]["num"])
                cols = cols[:2] + self.repeat_columns(columns=cols[2:5], num=max_num) + cols[5:]
            else:
                raise NotImplementedError(
                    f"The configuration file contains a key word ('{key}') that has not been configured in "
                    f"the {__class__.__name__} class yet. Aborting scenario creation...")

            # Update maximum number of batteries
            max_bat = max(max(self.config[key]["battery"]["num"]), max_bat)

            # Save columns
            columns[key] = cols

        # Define and insert all columns that come before the plants
        aftcols = self.make_list_from_nested_dict(self.config[key])
        aftkeys = ["battery", "ems"]
        for aftkey in aftkeys:
            # Get all columns that match the key
            cols = [col for col in aftcols if aftkey == col.split("/", 1)[0]]
            # Adjust the columns from "battery"
            if aftkey == "battery":
                del cols[1]
                cols.insert(0, f"{aftkey}/owner")
                cols = cols[:2] + self.repeat_columns(columns=cols[2:-1], num=max_bat) + [cols[-1]]
            # All columns that do not need to be adjusted
            elif aftkey in ["ems"]:
                pass
            else:
                raise NotImplementedError(
                    f"The configuration file contains a key word ('{aftkey}') that has not been configured in "
                    "the Sfhs class yet. Aborting scenario creation...")
            columns[aftkey] = cols

        # Combine all separate lists into one for the dataframe
        cols_df = []
        for _, cols in columns.items():
            cols_df += cols

        # Create dataframe with responding columns
        if self.method == 'config':
            # normal indexing
            self.df = pd.DataFrame(columns=cols_df)
        elif self.method == 'grid':
            # indexing matches the load sheet (all rows that are empty in owner as those are EVs and HPs)
            self.df = pd.DataFrame(index=self.agents.index, columns=cols_df)
        else:
            raise NotImplementedError(f"The method '{self.method}' has not been implemented yet. "
                                      f"Aborting scenario creation...")

        return self.df

    def add_pv(self):
        """
            Adds all PV producers
        """
        key = c.P_PV
        self.num_agents = self.config[f"{key}"]["general"]["number_of"]
        self.idx_start = len(self.df)

        if self.num_agents == 0:
            return

        # general
        self.fill_general(device=key)

        # pv
        self.fill_pv(device=key)

        # battery
        self.fill_battery(device=key)

        # mpc
        self.fill_ems(device=key)

    def add_wind(self):
        """
            Adds all wind producers
        """
        key = c.P_WIND
        self.num_agents = self.config[f"{key}"]["general"]["number_of"]

        if self.num_agents == 0:
            return

        # general
        self.fill_general(device=key)

        # wind
        self.fill_wind(device=key)

        # battery
        self.fill_battery(device=key)

        # mpc
        self.fill_ems(device=key)

    def add_fixed_gen(self):
        """
            Adds all wind producers
        """
        key = c.P_FIXED_GEN
        self.num_agents = self.config[f"{key}"]["general"]["number_of"]

        # general
        self.fill_general(device=key)

        if self.num_agents == 0:
            return

        # wind
        self.fill_fixed_gen(device=key)

        # battery
        self.fill_battery(device=key)

        # mpc
        self.fill_ems(device=key)

    def fill_general(self, device: str):
        """
            Fills all general columns
        """
        key = c.K_GENERAL
        config = self.config[f"{device}"][f"{key}"]
        self.idx_start = len(self.df)
        self.idx_end = self.idx_start + self.num_agents

        # add the required rows
        for i in range(self.idx_start, self.idx_end):
            # TODO: Throws a FutureWarning. That needs to be checked.
            self.df.loc[i] = np.nan

        # general
        self.df.loc[self.idx_start:self.idx_end, f"{key}/agent_id"] = f.gen_ids(n=self.num_agents)

    def fill_pv(self, device: str):
        """
            Fills all pv columns
        """
        key = c.P_PV
        config = self.config[f"{device}"][f"{key}"]

        # general
        self._add_general_info(key=key, config=config)

        # sizing
        max_num = max(config["num"])
        for num in range(max_num):
            # index list indicating ownership of device
            idx_list = self._get_idx_list(key=key, num=num, config=config)

            # sizing
            self.df.loc[self.idx_start:self.idx_end] = self._add_info_indexed(
                keys=[key, "sizing"], config=config["sizing"], df=self.df[self.idx_start:self.idx_end][:],
                idx_list=idx_list, appendix=f"_{num}")
            # postprocessing
            # power
            self.df.loc[self.idx_start:self.idx_end, f"{key}/sizing/power_{num}"] = self._calc_deviation(
                idx_list=idx_list, vals=self.df.loc[self.idx_start:self.idx_end, f"{key}/sizing/power_{num}"],
                distr=config["sizing"]["power_deviation"], method="absolute")
            self.df.loc[self.idx_start:self.idx_end, f"{key}/sizing/power_{num}"] = self._round_to_nth_digit(
                vals=self.df.loc[self.idx_start:self.idx_end, f"{key}/sizing/power_{num}"], n=self.n_digits)
            self.df[f"{key}/sizing/power_{num}"] = self.df[f"{key}/sizing/power_{num}"].astype('Int64')
            # file
            self.df[f"{key}/sizing/file_{num}"] = self._pick_files(
                list_type=self.df.loc[self.idx_start:self.idx_end, f"{key}/sizing/file_{num}"],
                device=f"{key}",
                input_path=os.path.join(self.input_path, key))
            # orientation
            self.df[f"{key}/sizing/orientation_{num}"] = self.df[f"{key}/sizing/orientation_{num}"].astype('Int16')
            # angle
            self.df[f"{key}/sizing/angle_{num}"] = self.df[f"{key}/sizing/angle_{num}"].astype('Int16')

        # forecast
        self.df.loc[self.idx_start:self.idx_end] = self._add_info_simple(keys=[key, "fcast"], config=config["fcast"],
                                                                         df=self.df[self.idx_start:self.idx_end][:])

    def fill_wind(self, device: str):
        """
            Fills all wind columns
        """
        key = c.P_WIND
        config = self.config[f"{device}"][f"{key}"]

        # general
        self._add_general_info(key=key, config=config)

        # sizing
        max_num = max(config["num"])
        for num in range(max_num):
            # index list indicating ownership of device
            idx_list = self._get_idx_list(key=key, num=num, config=config)

            # sizing
            self.df.loc[self.idx_start:self.idx_end] = self._add_info_indexed(
                keys=[key, "sizing"], config=config["sizing"], df=self.df[self.idx_start:self.idx_end][:],
                idx_list=idx_list, appendix=f"_{num}")
            # postprocessing
            # power
            self.df.loc[self.idx_start:self.idx_end, f"{key}/sizing/power_{num}"] = self._calc_deviation(
                idx_list=idx_list, vals=self.df.loc[self.idx_start:self.idx_end, f"{key}/sizing/power_{num}"],
                distr=config["sizing"]["power_deviation"], method="absolute")
            self.df.loc[self.idx_start:self.idx_end, f"{key}/sizing/power_{num}"] = self._round_to_nth_digit(
                vals=self.df.loc[self.idx_start:self.idx_end, f"{key}/sizing/power_{num}"], n=self.n_digits)
            self.df[f"{key}/sizing/power_{num}"] = self.df[f"{key}/sizing/power_{num}"].astype('Int64')
            # file
            self.df.loc[self.idx_start:self.idx_end, f"{key}/sizing/file_{num}"] = self._pick_files(
                list_type=self.df.loc[self.idx_start:self.idx_end, f"{key}/sizing/file_{num}"],
                device=f"{key}",
                input_path=os.path.join(self.input_path, key))

        # forecast
        self.df.loc[self.idx_start:self.idx_end] = self._add_info_simple(keys=[key, "fcast"], config=config["fcast"],
                                                                         df=self.df[self.idx_start:self.idx_end][:])

    def fill_fixed_gen(self, device: str):
        """
            Fills all fixed_gen columns
        """

        key = c.P_FIXED_GEN
        config = self.config[f"{device}"][f"{key}"]

        # general
        self._add_general_info(key=key, config=config)

        # sizing
        max_num = max(config["num"])
        for num in range(max_num):
            # index list indicating ownership of device
            idx_list = self._get_idx_list(key=key, num=num, config=config)

            # sizing
            self.df.loc[self.idx_start:self.idx_end] = self._add_info_indexed(
                keys=[key, "sizing"], config=config["sizing"], df=self.df[self.idx_start:self.idx_end][:],
                idx_list=idx_list, appendix=f"_{num}")
            # postprocessing
            # power
            self.df.loc[self.idx_start:self.idx_end, f"{key}/sizing/power_{num}"] = self._calc_deviation(
                idx_list=idx_list, vals=self.df.loc[self.idx_start:self.idx_end, f"{key}/sizing/power_{num}"],
                distr=config["sizing"]["power_deviation"], method="absolute")
            self.df.loc[self.idx_start:self.idx_end, f"{key}/sizing/power_{num}"] = self._round_to_nth_digit(
                vals=self.df.loc[self.idx_start:self.idx_end, f"{key}/sizing/power_{num}"], n=self.n_digits)
            self.df[f"{key}/sizing/power_{num}"] = self.df[f"{key}/sizing/power_{num}"].astype('Int64')
            # file
            self.df.loc[self.idx_start:self.idx_end, f"{key}/sizing/file_{num}"] = self._pick_files(
                list_type=self.df.loc[self.idx_start:self.idx_end, f"{key}/sizing/file_{num}"],
                device=f"{key}",
                input_path=os.path.join(self.input_path, key))

        # forecast
        self.df.loc[self.idx_start:self.idx_end] = self._add_info_simple(keys=[key, "fcast"], config=config["fcast"],
                                                                         df=self.df[self.idx_start:self.idx_end][:])

    def fill_battery(self, device: str):
        """
            Fills all battery columns
        """
        key = c.P_BATTERY
        config = self.config[f"{device}"][f"{key}"]

        # general
        self._add_general_info_dependent(key=key, config=config)

        # sizing
        max_num = max(config["num"])
        for num in range(max_num):
            # index list indicating ownership of device
            idx_list = self._get_idx_list(key=key, num=num, config=config)

            # sizing
            self.df.loc[self.idx_start:self.idx_end] = self._add_info_indexed(
                keys=[key, "sizing"], config=config["sizing"], df=self.df[self.idx_start:self.idx_end][:],
                idx_list=idx_list, appendix=f"_{num}")
            # postprocessing
            # power
            self.df.loc[self.idx_start:self.idx_end, f"{key}/sizing/power_{num}"] *= self.df[f"{device}/sizing/power_0"]
            self.df.loc[self.idx_start:self.idx_end, f"{key}/sizing/power_{num}"] = self._round_to_nth_digit(
                vals=self.df.loc[self.idx_start:self.idx_end, f"{key}/sizing/power_{num}"], n=self.n_digits)
            # capacity
            self.df.loc[self.idx_start:self.idx_end, f"{key}/sizing/capacity_{num}"] *= self.df[
                f"{device}/sizing/power_0"]
            self.df.loc[self.idx_start:self.idx_end, f"{key}/sizing/capacity_{num}"] = self._round_to_nth_digit(
                vals=self.df.loc[self.idx_start:self.idx_end, f"{key}/sizing/capacity_{num}"], n=self.n_digits)

    def fill_ems(self, device: str):
        """
            Fills all battery columns
        """
        key = c.K_EMS
        config = self.config[f"{device}"][f"{key}"]

        # general
        self.df.loc[self.idx_start:self.idx_end] = self._add_info_simple(keys=[key], config=config,
                                                                         df=self.df[self.idx_start:self.idx_end][:])

    def _get_idx_list(self, key: str, num: int, config: dict) -> list:
        """creates the index list for the given run"""

        # Check who owns the device
        list_owner = np.multiply(np.array(self.df.loc[self.idx_start:self.idx_end, f"{key}/num"] - (1 + num) >= 0), 1)
        list_owner = [np.nan if elem == 0 else elem for elem in list_owner]

        # Return according index list based on ownership to choose plants
        idx_list = self._gen_idx_list_from_distr(n=self.num_agents, distr=config["sizing"]["distribution"])
        idx_list = np.multiply(list_owner, idx_list)

        return [int(elem) if not np.isnan(elem) else np.nan for elem in idx_list]

    def _add_general_info(self, key: str, config: dict) -> None:

        # fields that exist for all plants
        self.df.loc[self.idx_start:self.idx_end, f"{key}/owner"] = 1
        self.df.loc[self.idx_start:self.idx_end, f"{key}/num"] = self._gen_dep_num_list(
            owner_list=self.df.loc[self.idx_start:self.idx_end, f"{key}/owner"], distr=config["num"])
        self.df.loc[self.idx_start:self.idx_end, f"{key}/num"] *= self.df[f"{key}/owner"]

    def _add_general_info_dependent(self, key: str, config: dict) -> None:

        # fields that exist for all plants
        self.df.loc[self.idx_start:self.idx_end, f"{key}/owner"] = 1
        self.df.loc[self.idx_start:self.idx_end, f"{key}/num"] = self._gen_dep_num_list(
            owner_list=self.df.loc[self.idx_start:self.idx_end, f"{key}/owner"], distr=config["num"])
        self.df.loc[self.idx_start:self.idx_end, f"{key}/owner"] = \
            (self.df.loc[self.idx_start:self.idx_end, f"{key}/num"] > 0) * 1

    def _add_general_info_bat(self, key: str):

        # find all potential owners of a battery system dependent on type
        # note: this setup considers the different dependencies for each type and loops through each separately
        agent_types = self.config["general"]["parameters"]["type"]
        list_owner = [0] * self.num
        list_num = [0] * self.num
        for idx, agent_type in enumerate(agent_types):
            # get all agents of given type
            list_type = list(self.df["general/parameters/type"] == agent_type)
            plants = self.config[f"{key}"]["share_dependent_on"][idx]
            # check which agents of that type have the dependent plants
            for device in plants:
                list_type = [ltype * lowner for ltype, lowner in zip(list_type, self.df[f"{device}/owner"])]
            # create list of owners and their number of plants and add them to the lists
            temp_owner = self._gen_dep_bool_list(list_bool=list_type,
                                                 share_ones=self.config[f"{key}"]["share"][idx])
            temp_num = self._gen_dep_num_list(owner_list=temp_owner,
                                              distr=[self.config[f"{key}"]["num"][idx]])
            list_owner = [lowner + towner for lowner, towner in zip(list_owner, temp_owner)]
            list_num = [lnum + tnum for lnum, tnum in zip(list_num, temp_num)]

            self.df.loc[self.idx_start:self.idx_end, f"{key}/owner"] = list_owner
            self.df.loc[self.idx_start:self.idx_end, f"{key}/num"] = list_num