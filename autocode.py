import re
import os
import time
import json
import base64
import random
import asyncio
import sqlite3
import datetime
import traceback
import itertools
import typing as t
from hashlib import md5

from pathlib import Path
from types import SimpleNamespace

import aiohttp
import discord

from discord import app_commands
from discord.ext import tasks, commands
####################################################################################################################### qwizz
DEBUG_HTTP = False
DATABASE: Path = Path(__file__).parent.joinpath("nitro.db") # Путь к файлу базы данных
BOT_TOKEN: str = "MTA2MTU2ODAwNjk4OTI5NTY4Ng.GE3BVn.Y_tJvvQUBDx1uX-t60IruZJzcNOsPxXf3u8dKw" # discord bot token https://discord.com/developers
QIWI_SECRET_KEY: str = "eyJ2ZXJzaW9uIjoiUDJQIiwiZGF0YSI6eyJwYXlpbl9tZXJjaGFudF9zaXRlX3VpZCI6Imd2MHRwMi0wMCIsInVzZXJfaWQiOiI3OTUzMjkwMzgyNSIsInNlY3JldCI6IjNkMGZkMDk2YTdlNGRlOTNiYThkMjZjZTE0ZjBjYzUxNzIwMDg3YTQ3NmVhMTAyNDczMTBlN2U1YmRiMmRjMTEifX0=" # base64 encoded qiwi private_key https://qiwi.com/p2p-admin/api
APPLICATION_ID: int = 1061568006989295686 # bot id
CLASSIC: str = ":b_nitroclass: " # classic emoji e.g: ":classic:"
FULL: str = ":b_nitrofull: "  # full_nitro emoji e.g: ":full:" 
NITRO: str = ""  # nitro emoji e.g: ":nitro:"
ADMIN_SERVER: int = 1022372152193855488 # id of admin server
ADMIN_ROLE: int = 1061550395018711050 # id of admin role
BUY_CHANNEL: int = 1061549789130526811 # id of buy log channel
OPLATA_CHANNEL: int = 1061549789130526811 # id of oplata log channel
OTZIVI_CHANNEL: str = "https://discord.gg/qwT8E8Ap"
#######################################################################################################################
xInputDictType = t.Dict[t.Union[str, int, bool, None, float], t.Union[str, int, bool, None, float]]
xInputDataT = t.Union[t.List[xInputDictType], xInputDictType]

class Table:
    def __init__(self, name: str, db: "SqlDatabase", *, created: t.Optional[bool] = None) -> None:
        with db.create_connection() as con:
            self.db = db
            cur = con.cursor()
            self.created = created
            self.name = name
            self._table_info = cur.execute(f"PRAGMA table_info({self.name});").fetchall()
            self._rows = cur.execute(f"SELECT * FROM {self.name}").fetchall()
    
    def __repr__(self) -> str:
        return f"<Table name={self.name} rows={len(self._rows)}>" 
    
    @property
    def exists(self) -> bool:
        with self.db.create_connection() as con:
            cur = con.cursor()
            try:
                return cur.execute(f"SELECT * FROM {self.name};") is not None
            except sqlite3.OperationalError:
                return False
    
    @property
    def rows(self) -> t.Optional[t.Dict[t.Any, t.Any]]:
        if not self.exists:
            return None
        tcolumns = [x[1] for x in self._table_info]
        data = {x: {tcolumns[z]: y[z] for z, _ in enumerate(tcolumns)} for x, y in enumerate(self._rows, start=1)}
        data["_types"] = {tcolumns[x]: y if y else "UNDEFINED" for x, y in enumerate([x[2] for x in self._table_info])}
        return json.dumps(data, indent=4)

    @property
    def columns(self) -> t.Optional[t.Dict[t.Any, t.Any]]:
        if not self.exists:
            return None
        return json.dumps({int(x[0]) + 1: {x[1]: x[2] if x[2] else "UNDEFINED"} for x in self._table_info}, indent=4)
    
    @property
    def pretty_print(self) -> t.Optional[str]:
        if not self.exists:
            return None
        columns = "0. | " + " | ".join([x[1] + f": {x[2] if x[2] else 'UNDEFINED'}" for x in self._table_info]) + " |\n"
        for x, row in enumerate(self._rows):
            columns += f"{x + 1}. | " + f"{' | '.join([str(x) for x in row])}" + " |\n"
        return f"table {self.name}:\n" + "=" * 50 + "\n" + columns + "=" * 50
    
    def drop(self) -> bool:
        with self.db.create_connection() as con:
            cur = con.cursor()
            try:
                cur.execute(f"DROP TABLE {self.name};")
            except sqlite3.OperationalError:
                return False
            return True

class DataBaseResponse:
    def __init__(self, status: bool, value: xInputDataT = None) -> None:
        self._status = status
        self._value = value if value is not None else None
    
    def __repr__(self) -> str:
        return f'<DataBaseResponse status={self._status}, value={self._value}>'
    
    def __len__(self) -> int:
        return len(self._value)
    
    @property
    def status(self) -> bool:
        return self._status
    
    @property
    def value(self) -> xInputDataT:
        return self._value

class SqlDatabase:
    def __init__(self, dbpath: str = None) -> None:
        self.dbpath = dbpath
    
    def create_connection(self, **kwargs) -> sqlite3.Connection:
        conn = sqlite3.connect(self.dbpath, **kwargs)
        conn.row_factory = sqlite3.Row
        return conn
    
    @property
    def tables(self) -> t.List[Table]:
        with self.create_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
            return [Table(x[0], db=self) for x in cur.fetchall()]
    
    def table(self, name: str, *columns) -> "Table":
        with self.create_connection() as con:
            cur = con.cursor()
            columns = f"({','.join(columns)})"
            try:
                created = not cur.execute(f"SELECT * FROM {name};") is not None
            except sqlite3.OperationalError: # table is not exist
                created = True
            cur.execute(f"CREATE TABLE IF NOT EXISTS {name}{columns};")
            return Table(name, created=created, db=self)
    
    def drop_table(self, name: str) -> bool:
        return Table(name, self).drop()
    
    def execute(self, query: str) -> sqlite3.Cursor:
        with self.create_connection() as con:
            cur = con.cursor()
            cur.execute(query)
            return cur
    
    def fetch(self, data: xInputDataT, table: str, mode: int = 1) -> DataBaseResponse:
        with self.create_connection() as con:
            cur = con.cursor()
            condition = " AND ".join([f"{x}=?" for x in data.keys()])
            sql = f"SELECT * FROM {table} {'WHERE ' + condition + ';' if data != {} else ';'}"
            cur.execute(sql, tuple([x for x in data.values()]))
            data = cur.fetchall()
            result = [dict(x) for x in data]
            result = result[0] if mode == 1 and result else result
        return DataBaseResponse(status=bool(result), value=result if result else None)
    
    def remove(self, data: xInputDataT, table: str, limit: t.Optional[t.Union[int, bool]] = None) -> DataBaseResponse:
        with self.create_connection() as con:
            if isinstance(data, list):
                for x in data:
                    a = self.remove(data=x, table=table, limit=limit)
                return DataBaseResponse(status=True, value=len(data))
            cur = con.cursor()
            condition = " AND ".join([f"{x}=?" for x in data.keys()])
            sql = f"DELETE FROM {table} {'WHERE ' + condition if data != {} else ''}" + (f" LIMIT {limit};" if limit else ";")
            cur.execute(sql, tuple([x for x in data.values()]))
            con.commit()
        return DataBaseResponse(status=bool(cur.rowcount), value=cur.rowcount if cur.rowcount else None)
    
    def add(self, data: xInputDataT, table: str) -> DataBaseResponse:
        with self.create_connection() as con:
            cur = con.cursor()
            columns = f"({', '.join([list(x.keys())[0] for x in json.loads(Table(table, db=self).columns).values()])})"
            if isinstance(data, list):
                values = f"{str([tuple([x for x in x.values()]) for x in data])[1:-1]};".replace(",)", ")")
            elif isinstance(data, dict):
                values = f"{str(tuple([x for x in data.values()]))};"
            sql = f"INSERT INTO {table} {columns} VALUES {values}"
            cur.execute(sql)
            con.commit()
        return DataBaseResponse(status=bool(cur.rowcount), value=data)
    
    def update(self, to_replace: xInputDataT, data: xInputDataT, table: str, limit: t.Optional[t.Union[int, bool]] = None) -> DataBaseResponse:
        with self.create_connection() as conn:
            values = ", ".join([f"{x} = {y}" if isinstance(y, int) else f"{x} = '{y}'" for x, y in data.items()])
            if values:
                cur = conn.cursor()
                condition = " AND ".join([f"{x}=?" for x in to_replace.keys()])
                sql = f"UPDATE {table} SET {values}{' WHERE ' + condition if condition else ''}{f' LIMIT {limit}' if limit else ''};"
                cur.execute(sql, tuple([x for x in to_replace.values()]))
                return DataBaseResponse(status=bool(cur.rowcount), value=cur.rowcount)
            raise ValueError("empty data to replace")
#######################################################################################################################
class ZalivView(discord.ui.View):
    class ZalivModal(discord.ui.Modal, title='Введите сумму пополнения:'):
        class ConfirmView(discord.ui.View):
            def __init__(self, *, type, args, timeout=180):
                super().__init__(timeout=timeout)
                self.type = type
                self.args = [{"code": x} for x in args]
                self.raw_args = args
            @discord.ui.button(emoji="✅", label="Да все верно.", style=discord.ButtonStyle.green)
            async def Yes(self, interaction: discord.Interaction, button: discord.ui.Button):
                try:
                    dbCategories = {
                        "Nitro full month": "Nitro_full_month",
                        "Nitro full Year": "Nitro_full_year",
                        "Nitro classic month": "Nitro_classic_month",
                        "Nitro classic year": "Nitro_classic_year"
                    }
                    await interaction.response.defer()
                    category = dbCategories.get(self.type)
                    res_add = interaction.client.db.add(self.args, category)
                    interaction.client.db.add([{"category": category, "code": x} for x in self.raw_args], "all_codes")
                    embed = discord.Embed(color=interaction.client.embed_color)
                    embed.title = "Успешно."
                    embed.description = f'`Добавлено {len(res_add.value)}/{len(self.args)} Указанных кодов в категорию {self.type}`'
                    res = interaction.client.db.fetch({}, "count")
                    if not res.status:
                        data = {'Nitro_classic_year': 0, 'Nitro_full_month': 0, 'Nitro_classic_month': 0, 'Nitro_full_year': 0}
                        data[category] = len(res_add.value)
                        interaction.client.db.add(data, "count")
                    else:
                        data = res.value
                        data[category] = len(res_add.value) + data[category]
                        interaction.client.db.remove({}, "count")
                        interaction.client.db.add(data, "count")
                    view = ZalivView.ZalivModal.BackView()
                    view.message = await interaction.message.edit(embed=embed, view=view)
                    self.message = view.message
                except Exception:
                    traceback.print_exc()
            @discord.ui.button(emoji="❌", label="Нет стоп.", style=discord.ButtonStyle.red)
            async def Nope(self, interaction: discord.Interaction, button: discord.ui.Button):
                await interaction.message.delete()
            @discord.ui.button(emoji="🔙", label="Назад", style=discord.ButtonStyle.gray, row=2)
            async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
                await interaction.response.defer()
                embed = discord.Embed(
                    title="Меню залива", 
                    description="""
                        **1.** `Nitro full month`
                        **2.** `Nitro full Year`
                        **3.** `Nitro classic month`
                        **4.** `Nitro classic Year`
                    """
                )
                if interaction.user.avatar:
                    embed.set_thumbnail(url=interaction.user.avatar.url)
                embed.color = interaction.client.embed_color
                view = ZalivView()
                view.message = await interaction.message.edit(embed=embed, view=view)
                self.message = view.message
            async def on_timeout(self) -> None:
                c = 0
                components = [x.label for x in list(itertools.chain([x.children for x in self.message.components]))[0] if isinstance(x, discord.components.Button)]
                x: discord.ui.Button
                for x in self.children:
                    if not x.style is discord.ButtonStyle.link:
                        if x.label in components:
                            c += 1
                            x.disabled = True
                if c:
                    for x in self.children:
                        x.disabled = True
                    await self.message.edit(view=self)
        class BackView(discord.ui.View):
            def __init__(self, *, timeout=180):
                super().__init__(timeout=timeout)
            @discord.ui.button(emoji="🔙", label="Выйти", style=discord.ButtonStyle.gray, row=2)
            async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
                await interaction.message.delete()
            async def on_timeout(self) -> None:
                c = 0
                components = [x.label for x in list(itertools.chain([x.children for x in self.message.components]))[0] if isinstance(x, discord.components.Button)]
                x: discord.ui.Button
                for x in self.children:
                    if not x.style is discord.ButtonStyle.link:
                        if x.label in components:
                            c += 1
                            x.disabled = True
                if c:
                    for x in self.children:
                        x.disabled = True
                    await self.message.edit(view=self)
        def __init__(self, title, timeout=None):
            super().__init__(timeout=timeout, title=title)
            self.pattern = re.compile(r"[A-z1-9]{5,50}")
        answer = discord.ui.TextInput(label='Коды ссылок.', style=discord.TextStyle.long, required=True, placeholder="Только КОДЫ ссылок через пробел")
        async def on_submit(self, interaction: discord.Interaction):
            await interaction.response.defer()
            codes = [x.replace("\n", "") for x in self.answer.value.split(' ') if x.replace("\n", "") != "" and self.pattern.fullmatch(x.replace("\n", ""))]
            embed = discord.Embed(color=interaction.client.embed_color)
            embed.title = "Подтверждение."
            description = f"**Вы собираетесь залить {self.title}:**\n"
            if len(codes):
                answer = [f"{x}\n" for x in codes]
                for y, x in enumerate(answer):
                    description += f"**{y+1}.** `https://discord.gift/{x}`"
                embed.description = description
                view = self.ConfirmView(type=self.title, args=codes)
                view.message = await interaction.message.edit(embed=embed, view=view)
                self.message = view.message
            else:
                embed.description = '`Не найдено кодов, похожих на коды от нитро`\n`(код должен быть от 5 до 50(че) символов и включать тольк символы от A до z и цифры от 1 до 9)`\n`Например у ссылки https://discord.gift/Jph5Z35XrcCj6HAw код Jph5Z35XrcCj6HAw`'
                view = self.BackView()
                view.message = await interaction.message.edit(embed=embed, view=view)
                self.message = view.message
    def __init__(self, *, timeout=180):
        super().__init__(timeout=timeout)
    @discord.ui.button(emoji=FULL, label="1", style=discord.ButtonStyle.green, row=2)
    async def full_month(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(self.ZalivModal("Nitro full month"))
    @discord.ui.button(emoji=FULL, label="2", style=discord.ButtonStyle.green, row=2)
    async def full_year(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(self.ZalivModal("Nitro full Year"))
    @discord.ui.button(emoji=CLASSIC, label="3", style=discord.ButtonStyle.green, row=2)
    async def classic_month(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(self.ZalivModal("Nitro classic month"))
    @discord.ui.button(emoji=CLASSIC, label="4", style=discord.ButtonStyle.green, row=2)
    async def classic_year(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(self.ZalivModal("Nitro classic year"))
    @discord.ui.button(emoji="🔙", label="Выйти", style=discord.ButtonStyle.gray, row=3)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()
#######################################################################################################################
class MainView(discord.ui.View):
    def __init__(self, *, timeout=180):
        super().__init__(timeout=timeout)
        self.add_item(discord.ui.Button(emoji="📝", label='Оставить отзыв о товаре.', url=OTZIVI_CHANNEL, row=2))
    @discord.ui.button(emoji="🛒", label="Магазин", style=discord.ButtonStyle.green)
    async def shop(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer()
            embed = discord.Embed(
                title="Магазин"
            )
            embed.description = "**Выберите категорию:**"
            if interaction.user.avatar:
                embed.set_thumbnail(url=interaction.user.avatar.url)
            embed.color = interaction.client.embed_color
            view = TovarView(interaction=interaction)
            view.message = await interaction.message.edit(embed=embed, view=view)
            self.message = view.message
        except Exception:
            traceback.print_exc()
    @discord.ui.button(emoji="💼", label="Профиль", style=discord.ButtonStyle.green)
    async def profile(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        res = interaction.client.get_profile(interaction.user.id)
        embed = discord.Embed(title="Основное меню", color=interaction.client.embed_color)
        description = ""
        description += f"> **Баланс**: `{res['balance']} RUB`\n"
        description += f"> **Потрачено**: `{res['spent']} RUB`\n"
        description += f"> **Куплено товаров**: `{res['bought']}`\n"
        embed.description = description
        view = ProfileView()
        view.message = await self.message.edit(embed=embed, view=view)
        self.message = view.message
    @discord.ui.button(emoji="🆘", label="Поддержка", style=discord.ButtonStyle.green)
    async def support(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed = discord.Embed(title="Поддержка", description=f"{interaction.user.mention} если у вас возникли вопросы по поводу оплаты или этого бота то пишите <@!728165963480170567> [`<@!728165963480170567>`]")
        if interaction.user.avatar:
            embed.set_thumbnail(url=interaction.user.avatar.url)
        embed.color = interaction.client.embed_color
        view = SupportView()
        view.message = await self.message.edit(embed=embed, view=view)
        self.message = view.message
    async def on_timeout(self) -> None:
        c = 0
        components = [x.label for x in list(itertools.chain([x.children for x in self.message.components]))[0] if isinstance(x, discord.components.Button)]
        x: discord.ui.Button
        for x in self.children:
            if not x.style is discord.ButtonStyle.link:
                if x.label in components:
                    c += 1
                    x.disabled = True
        if c:
            for x in self.children:
                x.disabled = True
            await self.message.edit(view=self)
class SupportView(discord.ui.View):
    def __init__(self, *, timeout=180):
        super().__init__(timeout=timeout)
    @discord.ui.button(emoji="🔙", label="Назад", style=discord.ButtonStyle.gray)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed = discord.Embed(title="Основное меню", description="Выберите категорию")
        if interaction.user.avatar:
            embed.set_thumbnail(url=interaction.user.avatar.url)
        embed.color = interaction.client.embed_color
        view = MainView()
        view.message = await self.message.edit(embed=embed, view=view)
        self.message = view.message
    async def on_timeout(self) -> None:
        c = 0
        components = [x.label for x in list(itertools.chain([x.children for x in self.message.components]))[0] if isinstance(x, discord.components.Button)]
        x: discord.ui.Button
        for x in self.children:
            if not x.style is discord.ButtonStyle.link:
                if x.label in components:
                    c += 1
                    x.disabled = True
        if c:
            for x in self.children:
                if not x.style is discord.ButtonStyle.link:
                    x.disabled = True
            await self.message.edit(view=self)
class ProfileView(discord.ui.View):
    class BackView(discord.ui.View):
        def __init__(self, *, timeout=180):
            super().__init__(timeout=timeout)
        @discord.ui.button(emoji="🔙", label="Назад", style=discord.ButtonStyle.gray)
        async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.defer()
            res = interaction.client.get_profile(interaction.user.id)
            embed = discord.Embed(title="Основное меню", color=interaction.client.embed_color)
            description = ""
            description += f"> **Баланс**: `{res['balance']} RUB`\n"
            description += f"> **Потрачено**: `{res['spent']} RUB`\n"
            description += f"> **Куплено товаров**: `{res['bought']}`\n"
            embed.description = description
            view = ProfileView()
            view.message = await self.message.edit(embed=embed, view=view)
            self.message = view.message
        async def on_timeout(self) -> None:
            c = 0
            components = [x.label for x in list(itertools.chain([x.children for x in self.message.components]))[0] if isinstance(x, discord.components.Button)]
            x: discord.ui.Button
            for x in self.children:
                if not x.style is discord.ButtonStyle.link:
                    if x.label in components:
                        c += 1
                        x.disabled = True
            if c:
                for x in self.children:
                    x.disabled = True
                await self.message.edit(view=self)
    def __init__(self, *, timeout=180):
        super().__init__(timeout=timeout)
    @discord.ui.button(emoji="🔙", label="Назад", style=discord.ButtonStyle.gray, row=2)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed = discord.Embed(title="Основное меню", description="Выберите категорию")
        if interaction.user.avatar:
            embed.set_thumbnail(url=interaction.user.avatar.url)
        embed.color = interaction.client.embed_color
        view = MainView()
        view.message = await interaction.message.edit(embed=embed, view=view)
        self.message = view.message
    @discord.ui.button(emoji="💸", label="Пополнить баланс", style=discord.ButtonStyle.green, row=1)
    async def popolnit(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(color=interaction.client.embed_color)
        description = "**Выберите платежную систему:**"
        embed.description = description
        await interaction.response.defer()
        view = OplataTypeView(interaction=interaction)
        view.message = await interaction.message.edit(embed=embed, view=view)
        self.message = view.message
    async def on_timeout(self) -> None:
        c = 0
        components = [x.label for x in list(itertools.chain([x.children for x in self.message.components]))[0] if isinstance(x, discord.components.Button)]
        x: discord.ui.Button
        for x in self.children:
            if not x.style is discord.ButtonStyle.link:
                if x.label in components:
                    c += 1
                    x.disabled = True
        if c:
            for x in self.children:
                x.disabled = True
            await self.message.edit(view=self)
class NitroTovarView(discord.ui.View):
    def __init__(self, interaction, *, timeout=180):
        super().__init__(timeout=timeout)
        self.add_item(self.NitroSelect(interaction))
    class BuyView(discord.ui.View):
        def __init__(self, *, requested_price, interaction, timeout=180):
            self.requested_price = requested_price
            super().__init__(timeout=timeout)
            dbCategories = {}
            prices = interaction.client.get_prices()
            for x, y in prices.items():
                dbCategories[y] = x
            button = discord.ui.Button(emoji="💸", label="Приобрести.", style=discord.ButtonStyle.green, row=1)
            res = interaction.client.get_profile(interaction.user.id)
            if requested_price > res['balance']:
                button.disabled = True
                button.label = "Пополните баланс в профиле для покупки."
            if not interaction.client.check_for_available(dbCategories.get(requested_price))[0]:
                if not button.disabled:
                    button.disabled = True
                button.label = "Нет в наличии."
            button.callback = self.callback
            self.add_item(button)
            self.type = dbCategories.get(requested_price)
        async def on_timeout(self, forced: bool = False) -> None:
            if forced:
                return
            c = 0 # мегаватикус
            components = [x.label for x in list(itertools.chain([x.children for x in self.message.components]))[0] if isinstance(x, discord.components.Button)]
            x: discord.ui.Button
            for x in self.children:
                if not x.style is discord.ButtonStyle.link:
                    if x.label in components:
                        c += 1
                        x.disabled = True
            if c:
                for x in self.children:
                    x.disabled = True
                await self.message.edit(view=self)
        @discord.ui.button(emoji="🔙", label="Назад.", style=discord.ButtonStyle.gray, row=2)
        async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
            try:
                await interaction.response.defer()
                count = interaction.client.get_count()
                prices = interaction.client.get_prices()
                nitros_prices = []
                nitros = interaction.client.nitros
                for x in nitros:
                    x[1] = prices.get(x[2])
                    nitros_prices.append(x)
                embed = discord.Embed(
                    title="Магазин"
                )
                description = ""
                s = False
                classic = None
                full = None
                guild = interaction.client.get_guild(ADMIN_SERVER)
                for x in guild.emojis:
                    if "lassic" in x.name:
                        classic = x
                    elif "full" in x.name:
                        full = x
                for x, y, z in nitros_prices:
                    if not x.endswith(".") and not s:
                        s = True
                        description += '\n'
                    description += f"{str(classic)} " if "lassic" in x else f"{str(full)} "
                    description += f"`{x if x.endswith('.') else x + '.'}`**:** **Кол-во: {count.get(z)}** | **_Цена: {y}_**\n"
                embed.description = description
                if interaction.user.avatar:
                    embed.set_thumbnail(url=interaction.user.avatar.url)
                embed.color = interaction.client.embed_color
                view = NitroTovarView(interaction)
                view.message = await interaction.message.edit(embed=embed, view=view)
                self.message = view.message
            except Exception:
                traceback.print_exc()
        async def callback(self, interaction: discord.Interaction):
            embed = discord.Embed(title="Успешно", description="`Сейчас вам придет сообщение с купленным товаром.`")
            await self.on_timeout(forced=True)
            if interaction.user.avatar:
                embed.set_thumbnail(url=interaction.user.avatar.url)
            embed.color = interaction.client.embed_color
            try:
                code = interaction.client.yield_from_database(self.type, self.requested_price, interaction.user.id)
            except Exception:
                traceback.print_exc()
            if code:
                await interaction.response.send_message("https://discord.gift/" + code["code"])
                self.message = await interaction.message.edit(embed=embed, view=None)
                channel = interaction.client.get_channel(BUY_CHANNEL)
                try:
                    await channel.send(f"**Пользователь** `{interaction.user}` | `[<@!{interaction.user.id}>]` Только что купил {self.type} за {self.requested_price}RUB")
                except Exception:
                    ...
                return
            return await interaction.response.send_message("`Что то пошло не так.`\n`Выглядит так, как будто прямо перед вами купили последнее нитро.`\n`Баланс не изменился.`")
    class NitroSelect(discord.ui.Select):
        def __init__(self, interaction):
            self.message = interaction.message
            res = interaction.client.db.fetch({"id": interaction.user.id}, "profiles")
            self.balance = 0
            self.count = interaction.client.get_count()
            if res.status:
                self.balance = res.value.get("balance")
            self.nitros = interaction.client.nitros
            prices = interaction.client.get_prices()
            self.nitros_prices = []
            for x in self.nitros:
                x[1] = prices.get(x[2])
                self.nitros_prices.append(x)
            self.nitros = self.nitros_prices
            options=[discord.SelectOption(label=x[0], emoji=CLASSIC if "lassic" in x[0] else FULL, description="Только качественный товар." if x[0].endswith(".") else "Только качественный товар.") for x in self.nitros]
            super().__init__(placeholder="Выберите товар.", max_values=1, min_values=1, options=options)
        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer()
            try:
                self.embeds = {
                    x: [discord.Embed(
                        title=f"{x + '' if x.endswith('.') else x + ''}",
                        description=f"> **Цена**: `{y} RUB` **Ваш баланс**: `{self.balance if self.balance else 0} RUB`\n> **Вы получаете товар отдельным сообщением сразу после покупки.**\n> `Количество:` **{self.count.get(z)}**",
                        color=interaction.client.embed_color
                    ), y] for x, y, z in self.nitros
                }
                embed = self.embeds.get(self.values[0])
                view = NitroTovarView.BuyView(requested_price=embed[1], interaction=interaction)
                view.message = await interaction.message.edit(embed=embed[0], view=view)
                self.message = view.message
            except Exception:
                traceback.print_exc()
    @discord.ui.button(emoji="🔙", label="Назад", style=discord.ButtonStyle.gray, row=2)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer()
            embed = discord.Embed(
                title="Магазин"
            )
            embed.description = "**Выберите категорию:**"
            if interaction.user.avatar:
                embed.set_thumbnail(url=interaction.user.avatar.url)
            embed.color = interaction.client.embed_color
            view = TovarView(interaction=interaction)
            view.message = await interaction.message.edit(embed=embed, view=view)
            self.message = view.message
        except Exception:
            traceback.print_exc()
    async def on_timeout(self) -> None:
        c = 0
        components = [x.label if isinstance(x, discord.components.Button) else x.placeholder for x in list(itertools.chain([x.children for x in self.message.components]))[0]]
        x: discord.ui.Button
        for x in self.children:
            if isinstance(x, discord.ui.Button):
                if not x.style is discord.ButtonStyle.link:
                    if x.label in components:
                        c += 1
                        x.disabled = True
            elif isinstance(x, discord.ui.Select):
                if x.placeholder in components:
                    c += 1
                    x.disabled = True
        if c > 0:
            for x in self.children:
                x.disabled = True
            await self.message.edit(view=self)
class OplataTypeView(discord.ui.View):
    class BackView(discord.ui.View):
        def __init__(self, timeout=180):
            super().__init__(timeout=timeout)
        @discord.ui.button(style=discord.ButtonStyle.gray, emoji="🔙", label="Назад.", row=2)
        async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.defer()
            try:
                res = interaction.client.get_profile(interaction.user.id)
                embed = discord.Embed(title="Основное меню", color=interaction.client.embed_color)
                description = ""
                description += f"> **Баланс**: `{res['balance']} RUB`\n"
                description += f"> **Потрачено**: `{res['spent']} RUB`\n"
                description += f"> **Куплено товаров**: `{res['bought']}`\n"
                embed.description = description
                view = ProfileView()
                view.message = await self.message.edit(embed=embed, view=view)
                self.message = view.message
            except Exception:
                traceback.print_exc()
        async def on_timeout(self) -> None:
            c = 0
            components = [x.label if isinstance(x, discord.components.Button) else x.placeholder for x in list(itertools.chain([x.children for x in self.message.components]))[0]]
            x: discord.ui.Button
            for x in self.children:
                if isinstance(x, discord.ui.Button):
                    if not x.style is discord.ButtonStyle.link:
                        if x.label in components:
                            c += 1
                            x.disabled = True
                elif isinstance(x, discord.ui.Select):
                    if x.placeholder in components:
                        c += 1
                        x.disabled = True
            if c > 0:
                for x in self.children:
                    x.disabled = True
                await self.message.edit(view=self)
    def __init__(self, *, interaction, timeout=180):
        super().__init__(timeout=timeout)
        class OplataSelect(discord.ui.Select):
            def __init__(self, interaction: discord.Interaction):
                options=[discord.SelectOption(label="Qiwi", emoji="🥝", description="Оплата по киви.")]
                super().__init__(placeholder="Выберите платежную систему.", max_values=1, min_values=1, options=options)
            async def callback(self, interaction: discord.Interaction):
                try:
                    if self.values[0] == "Qiwi":
                        class QiwiModal(discord.ui.Modal):
                            def __init__(self, timeout=None):
                                super().__init__(timeout=timeout, title="Введите сумму пополнения:")
                            answer = discord.ui.TextInput(label='Сумма поплнения.', style=discord.TextStyle.short, required=True, placeholder="Сумма цифрами: ")
                            async def on_submit(self, interaction: discord.Interaction) -> None:
                                try:
                                    try:
                                        self.value = int(self.answer.value)
                                    except (ValueError, Exception):
                                        return await interaction.response.send_message("`Что то пошло не так...`\n`Попробуйте снова...`")
                                    s = interaction.client.session
                                    value = str(float(self.value))
                                    billid = "".join([[x[0:7] + "-", x[7:16] + "-", x[16:23] + "-", x[23:32]] for x in [md5(os.urandom(random.randint(50, 100))).hexdigest()]][0])
                                    params = {
                                        'amount': {
                                            'currency': 'RUB',
                                            'value': value
                                        },
                                        "comment": "by MegaWatt_#1114", # Не изменять. :skull:
                                        'expirationDateTime': str(datetime.datetime.now() + datetime.timedelta(minutes=15)).split(" ")[0] + "T" +str(datetime.datetime.now() + datetime.timedelta(minutes=10)).split(" ")[1].split(".")[0] + "+03:00"
                                    }
                                    r = await s.put(f"https://api.qiwi.com/partner/bill/v1/bills/{billid}", json=params)
                                    url = None
                                    if r.status == 200:
                                        url = (await r.json())["payUrl"]
                                    embed = discord.Embed(color=interaction.client.embed_color)
                                    description = ""
                                    description = f"{interaction.user.mention} `Счет сформирован.\nДля оплаты нажмите на кнопку ниже.`\n"
                                    description += f"**После оплаты подождите 1 минуту для того чтобы бот обработал платеж.**\n`Счет действителен 10 минут.`"
                                    interaction.client.db.add({"user_id": interaction.user.id, "billid": billid, "sum": int(float(value)), "date": int(datetime.datetime.now().timestamp())}, "transactions")
                                    embed.description = description
                                    view = OplataTypeView.BackView()
                                    view.add_item(discord.ui.Button(style=discord.ButtonStyle.link, url=url, label="Перейти к оплате.", emoji="💸", row=1))
                                    await interaction.response.defer()
                                    view.message = await interaction.message.edit(embed=embed, view=view)
                                    self.message = view.message
                                except Exception:
                                    traceback.print_exc()
                        await interaction.response.send_modal(QiwiModal())
                except Exception:
                    traceback.print_exc()
        self.add_item(OplataSelect(interaction=interaction))
    async def on_timeout(self) -> None:
        c = 0
        components = [x.label if isinstance(x, discord.components.Button) else x.placeholder for x in list(itertools.chain([x.children for x in self.message.components]))[0]]
        x: discord.ui.Button
        for x in self.children:
            if isinstance(x, discord.ui.Button):
                if not x.style is discord.ButtonStyle.link:
                    if x.label in components:
                        c += 1
                        x.disabled = True
            elif isinstance(x, discord.ui.Select):
                if x.placeholder in components:
                    c += 1
                    x.disabled = True
        if c > 0:
            for x in self.children:
                x.disabled = True
            await self.message.edit(view=self)
class TovarView(discord.ui.View):
    def __init__(self, *, interaction, timeout: t.Optional[float] = 180):
        self.message = interaction.message
        super().__init__(timeout=timeout)
        class TovarSelect(discord.ui.Select):
            def __init__(self, *, interaction):
                options= [discord.SelectOption(label="Discord Nitro", emoji=NITRO, description="Всякие плюшки для дискорда.")]
                super().__init__(placeholder="Выберите категорию.", max_values=1, min_values=1, options=options, row=1)
            async def callback(self, interaction: discord.Interaction):
                await interaction.response.defer()
                try:
                    if self.values[0] == "Discord Nitro":
                        count = interaction.client.get_count()
                        prices = interaction.client.get_prices()
                        nitros_prices = []
                        nitros = interaction.client.nitros
                        for x in nitros:
                            x[1] = prices.get(x[2])
                            nitros_prices.append(x)
                        embed = discord.Embed(
                            title="Магазин"
                        )
                        description = ""
                        s = False
                        classic = None
                        full = None
                        guild = interaction.client.get_guild(ADMIN_SERVER)
                        for x in guild.emojis:
                            if "lassic" in x.name:
                                classic = x
                            elif "full" in x.name:
                                full = x
                        for x, y, z in nitros_prices:
                            if not x.endswith(".") and not s:
                                s = True
                                description += '\n'
                            description += f"{str(classic)} " if "lassic" in x else f"{str(full)} "
                            description += f"`{x if x.endswith('.') else x}`**:** **Кол-во: {count.get(z)}** | **_Цена: {y}_**\n"
                        embed.description = description
                        if interaction.user.avatar:
                            embed.set_thumbnail(url=interaction.user.avatar.url)
                        embed.color = interaction.client.embed_color
                        view = NitroTovarView(interaction)
                        view.message = await interaction.message.edit(embed=embed, view=view)
                        self.message = view.message
                except Exception:
                    traceback.print_exc()
        self.add_item(TovarSelect(interaction=interaction))
    async def on_timeout(self) -> None:
        c = 0
        components = [x.label if isinstance(x, discord.components.Button) else x.placeholder for x in list(itertools.chain([x.children for x in self.message.components]))[0]]
        x: discord.ui.Button
        for x in self.children:
            if isinstance(x, discord.ui.Button):
                if not x.style is discord.ButtonStyle.link:
                    if x.label in components:
                        c += 1
                        x.disabled = True
            elif isinstance(x, discord.ui.Select):
                if x.placeholder in components:
                    c += 1
                    x.disabled = True
        if c > 0:
            for x in self.children:
                x.disabled = True
            await self.message.edit(view=self)
    @discord.ui.button(emoji="🔙", label="Назад", style=discord.ButtonStyle.gray, row=2)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed = discord.Embed(title="Основное меню", description="Выберите категорию")
        if interaction.user.avatar:
            embed.set_thumbnail(url=interaction.user.avatar.url)
        embed.color = bot.embed_color
        view = MainView()
        view.message = await interaction.followup.send(embed=embed, view=view)
#######################################################################################################################
class NitroAutoBot(commands.Bot):
    def __init__(self, **kwargs) -> None:
        print("--------------------------------------------------------")
        super().__init__(**kwargs)
        self.path = Path(__file__).parent
        self.session = None
        self.db = SqlDatabase("nitro.db")
        try:
            print("Qiwi Привязан к номеру:", "+" + json.loads(base64.b64decode(QIWI_SECRET_KEY.encode("ascii")).decode("utf-8"))["data"]["user_id"]) # Стилер
        except (Exception, KeyError) as e:
            raise SystemExit(f"SystemExit: {e}")
        self.embed_color = discord.Color.from_str("0xe0ffff")
        self.nitros =  [
            ["Nitro full 1 month.", 170, "Nitro_full_month"], ["Nitro full 1 Year.", 1499, "Nitro_full_year"], 
            ["Nitro Classic 1 Month.", 119, "Nitro_classic_month"], ["Nitro Classic 1 Year.", 999, "Nitro_classic_year"]
        ]
        try:
            if DATABASE.stat().st_size == 0:
                ...
        except FileNotFoundError:
            with open(DATABASE, "a") as _:
                ...
        finally:
            if DATABASE.stat().st_size == 0:
                for _, _, x in self.nitros:
                    self.db.table(x, "code TEXT")
                self.db.table("all_codes", "category TEXT", "code TEXT")
                self.db.table("profiles", "id INT", "balance INT", "bought INT", "spent INT")
                self.db.table("count", 'Nitro_classic_year INT', 'Nitro_full_month INT', 'Nitro_classic_month INT', 'Nitro_full_year INT')
                self.db.table("transactions", "user_id INT", "billid TEXT", "sum INT", "date INT")
                self.db.table("prices", "Nitro_full_month INT", "Nitro_full_year INT", "Nitro_classic_month INT", "Nitro_classic_year INT")
        print("DataBase connection appeared.")
    
    async def sync(self, *args, **kwargs) -> None:
        # self.tree.copy_global_to(guild=discord.Object(id=1000466637478178910))
        await self.tree.sync(*args, **kwargs) # guild=discord.Object(id=1000466637478178910)
    
    async def setup_hook(self) -> None:
        # await self.sync(guild=discord.Object(id=ADMIN_SERVER))
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        self.session.headers.update({
            "Authorization": "Bearer " + QIWI_SECRET_KEY,
            "user-agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:106.0) Gecko/20100101 Firefox/106.0", # пон
            "Content-Type": "application/json"
        })
    
    def get_profile(self, discord_id: int) -> t.Dict[str, int]:
        res = self.db.fetch({"id": discord_id}, "profiles")
        bal = wastes = bought = 0
        if res.status:
            bal = res.value['balance']
            wastes = res.value['spent']
            bought = res.value['bought']
        return {"balance": bal, "spent": wastes, "bought": bought}
    
    def check_for_available(self, category: str) -> bool:
        res = self.db.fetch({}, category)
        if res.status:
            return [res.status, len(res.value)]
        return [res.status, 0]
    
    def yield_from_database(self, category: str, rip_balance: int, id: int) -> bool:
        code = self.db.fetch({}, category)
        val = self.db.fetch({"id": id}, "profiles").value
        val["balance"] -= rip_balance
        val["spent"] += rip_balance
        val["bought"] += 1
        self.db.remove({"id": id}, "profiles")
        self.db.add(val, "profiles")
        if code.status:
            self.db.remove({"code": code.value["code"]}, category)
            self.db.remove({"code": code.value["code"]}, "all_codes")
            data = self.db.fetch({}, "count").value
            data[category] -= 1
            self.db.remove({}, "count")
            self.db.add(data, "count")
            return code.value
        return code.status

    def get_count(self):
        res = self.db.fetch({}, "count")
        if not res.status:
            return {
                'Nitro_classic_year': 0, 'Nitro_full_month': 0,
                'Nitro_classic_month': 0, 'Nitro_full_year': 0
            }
        return res.value

    def get_prices(self):
        res = self.db.fetch({}, "prices")
        if not res.status:
            data = {"Nitro_full_month": 170, "Nitro_full_year": 1499, "Nitro_classic_month": 119, "Nitro_classic_year": 999}
            self.db.add(data, "prices")
            return data
        return res.value

    def set_price(self, price: int, category: str) -> None:
        data = self.get_prices()
        self.db.remove({}, "prices")
        data[category] = price
        self.db.add(data, "prices")
#######################################################################################################################
async def callback(session: aiohttp.ClientSession, trace_config_ctx: SimpleNamespace, trace: aiohttp.TraceRequestEndParams):
    if DEBUG_HTTP:
        print(f'[{datetime.datetime.now().strftime("%H:%M:%S")}] Sent {trace.method} with status {trace.response.status} to {(str(trace.url)[0:100] + "...") if len(str(trace.url)) > 100 else trace.url}')
tc = aiohttp.TraceConfig()
tc.on_request_end.append(callback)

panel = discord.Object(id=ADMIN_SERVER)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = NitroAutoBot(
    http_trace=tc,
    command_prefix=None, 
    intents=intents,
    status=discord.Status.online,
    activity=discord.Game(name="/start"),
    application_id=APPLICATION_ID,
    qiwi_secret=QIWI_SECRET_KEY
)
dbCategories = [
    "Nitro_full_month", "Nitro_full_year",
    "Nitro_classic_month", "Nitro_classic_year",
]

@tasks.loop(seconds=60)
async def check_paid():
    try:
        s = bot.session
        res = bot.db.fetch({}, "transactions", mode=2)
        if res.status:
            for x in res.value:
                r = await s.get(f"https://api.qiwi.com/partner/bill/v1/bills/{x['billid']}")
                ispaid = (await r.json())["status"]["value"] == "PAID"
                if datetime.datetime.now().timestamp() - x["date"] > 900 and not ispaid:
                    bot.db.remove({"billid": x['billid']}, "transactions")
                    continue
                if ispaid:
                    bot.db.remove({"billid": x['billid']}, "transactions")
                    res = bot.db.fetch({"id": x["user_id"]}, "profiles")
                    if res.status:
                        value = res.value
                        bot.db.remove({"id": x["user_id"]}, "profiles")
                        value["balance"] += int(x["sum"])
                        bot.db.add(value, "profiles")
                    else:
                        bot.db.add({"id": x["user_id"], "balance": int(x["sum"]), "bought": 0, "spent": 0}, "profiles")
                    print(x["user_id"], "added", x["sum"], 'RUB', x["date"])
                    channel = bot.get_channel(OPLATA_CHANNEL)
                    user = await bot.fetch_user(x["user_id"])
                    if user is not None:
                        userid2 = user.id
                    else:
                        userid2 = None
                    try:
                        await channel.send(f"**Пользователь** `{user}` | `[<@!{userid2 if userid2 else x['user_id']}>]` Только что пополнил баланс на сумму {int(x['sum'])} RUB")
                    except Exception:
                        ...
                    a = "\n"
                    amount = x['sum']
                    embed = discord.Embed(
                        color=bot.embed_color,
                        title="Пополнение счета.",
                        description=f"{f'{user.mention}{a}`На ваш счет зачислено {amount} RUB`' if user else f'`<@!{userid2}>`{a}`На ваш счет зачислено {amount} RUB`'}"
                    )
                    try:
                        await user.send(embed=embed)
                    except Exception:
                        pass
    except Exception:
        traceback.print_exc()

@bot.tree.command(name = "start", description="Раскрой потенциал нитро!")
async def start(interaction: discord.Interaction):
    if interaction.guild:
        return await interaction.response.send_message("Эта команда может использоваться только в личных сообщениях бота.", ephemeral=True)
    await interaction.response.defer()
    print(interaction.user, "Just used /start!")
    embed = discord.Embed(title="Основное меню", description="Выберите категорию")
    if interaction.user.avatar:
        embed.set_thumbnail(url=interaction.user.avatar.url)
    embed.color = bot.embed_color
    view = MainView()
    view.message = await interaction.followup.send(embed=embed, view=view)

@bot.tree.command(name = "zaliv", description="Fiksiki", guild=panel)
async def zaliv(interaction: discord.Interaction):
    guild = interaction.client.get_guild(ADMIN_SERVER)
    role = discord.utils.get(guild.roles, id=ADMIN_ROLE)
    member = guild.get_member(interaction.user.id)
    if member is None or role not in member.roles:
        return await interaction.response.send_message("Вы не имеете права использовать эту команду!", ephemeral=True)
    await interaction.response.defer()
    embed = discord.Embed(
        title="Меню залива", 
        description="""
            **1.** `Nitro full month`
            **2.** `Nitro full Year`
            **3.** `Nitro classic month`
            **4.** `Nitro classic Year`
        """
    )
    if interaction.user.avatar:
        embed.set_thumbnail(url=interaction.user.avatar.url)
    embed.color = bot.embed_color
    view = ZalivView()
    view.message = await interaction.followup.send(embed=embed, view=view)

@bot.tree.command(name="codes", description="Все подарочные коды нитро в базе данных", guild=panel)
async def codes(interaction: discord.Interaction):
    guild = interaction.client.get_guild(ADMIN_SERVER)
    role = discord.utils.get(guild.roles, id=ADMIN_ROLE)
    member = guild.get_member(interaction.user.id)
    if member is None or role not in member.roles:
        return await interaction.response.send_message("Вы не имеете права использовать эту команду!", ephemeral=True)
    await interaction.response.defer()
    res = bot.db.fetch({}, "all_codes", mode=2)
    if res.status:
        embed = discord.Embed(
            title="Все коды нитро в базе данных.",
            color=bot.embed_color
        )
        description = ""
        for x, y in enumerate(res.value):
            description += f"**{x+1}.** `{y['code']}`**:** `{y['category']}`\n"
        embed.description = description
        return await interaction.followup.send(embed=embed)
    embed = discord.Embed(title="Внимание.", description="`Подарочных кодов в базе не найдено.`", color=discord.Colour.red())
    return await interaction.followup.send(embed=embed)

@bot.tree.command(name = "remove_code", description = "Этой командой можно удалить подарочный код из базы данных.", guild=panel)
async def remove_code(interaction: discord.Interaction, code: str):
    guild = interaction.client.get_guild(ADMIN_SERVER)
    role = discord.utils.get(guild.roles, id=ADMIN_ROLE)
    member = guild.get_member(interaction.user.id)
    if member is None or role not in member.roles:
        return await interaction.response.send_message("Вы не имеете права использовать эту команду!", ephemeral=True)
    await interaction.response.defer()
    res = bot.db.fetch({"code": code}, "all_codes")
    if res.status:
        bot.db.remove({"code": code}, "all_codes")
        bot.db.remove({"code": code}, res.value["category"])
        a = bot.db.fetch({}, "count").value
        a[res.value["category"]] -= 1
        bot.db.remove({}, "count")
        bot.db.add(a, "count")
    embed = discord.Embed(
        title="Удаление подарочного кода.", 
        description=f'`Код {code} успешно удален из категории {res.value["category"]}`\n' if res.status else f"`Код {code} не найден в базе данных.`",
        color=bot.embed_color
    )
    await interaction.followup.send(embed=embed)

@bot.tree.command(name = "add_bal", description="Добавить кому то денег на покупку нитро.", guild=panel)
async def add_bal(interaction: discord.Interaction, user: discord.User, balance: int) -> None:
    guild = interaction.client.get_guild(ADMIN_SERVER)
    role = discord.utils.get(guild.roles, id=ADMIN_ROLE)
    member = guild.get_member(interaction.user.id)
    if member is None or role not in member.roles:
        return await interaction.response.send_message("Вы не имеете права использовать эту команду!", ephemeral=True)
    res = bot.db.fetch({"id": user.id}, "profiles")
    if not res.status:
        bot.db.add({"id": user.id, "balance": balance, "bought": 0, "spent": 0}, "profiles")
    else:
        value = res.value
        value["balance"] += balance
        bot.db.remove({'id': user.id}, "profiles")
        bot.db.add(value, "profiles")
    await interaction.response.defer()
    embed = discord.Embed(color=discord.Colour.green())
    embed.title = "Успешно"
    embed.description = f"**Баланс пользователя** `{user}` | `[<@!{user.id}>]`\n**Успешно пополнен на** `{balance} RUB`"
    await interaction.followup.send(embed=embed)

@bot.tree.command(name = "remove_bal", description="Убрать у кого то определенную сумму денег.", guild=panel)
async def remove_bal(interaction: discord.Interaction, user: discord.User, balance: int) -> None:
    guild = interaction.client.get_guild(ADMIN_SERVER)
    role = discord.utils.get(guild.roles, id=ADMIN_ROLE)
    member = guild.get_member(interaction.user.id)
    if member is None or role not in member.roles:
        return await interaction.response.send_message("Вы не имеете права использовать эту команду!", ephemeral=True)
    res = bot.db.fetch({"id": user.id}, "profiles")
    if not res.status:
        bot.db.add({"id": user.id, "balance": balance, "bought": 0, "spent": 0}, "profiles")
        return await interaction.response.send_message("`Пользователя нет в базе (добавлен в нее с балансом 0)`", ephemeral=True)
    else:
        a = False
        value = res.value
        value["balance"] -= balance
        if value["balance"] < 0:
            a = True
            value["balance"] = 0
        bot.db.remove({'id': user.id}, "profiles")
        bot.db.add(value, "profiles")
    await interaction.response.defer()
    embed = discord.Embed(color=discord.Colour.green())
    embed.title = "Успешно"
    if not a:
        embed.description = f"**Баланс пользователя** {user} | `[<@!{user.id}>]`\n**Успешно изменен на** `{balance} RUB`\n`Теперь у него {value['balance']} RUB`"
    else:
        embed.description = f"**Баланс пользователя** {user} | `[<@!{user.id}>]`\n**был уменьшен до 0**"
    await interaction.followup.send(embed=embed)

@bot.tree.command(name = "profile", description="Профиль пользователя.", guild=panel)
async def profile(interaction: discord.Interaction, user: discord.User) -> None:
    try:
        res = bot.db.fetch({"id": user.id}, "profiles")
        if not res.status:
            return await interaction.response.send_message("`Пользователя нет в базе (пустой профиль)`", ephemeral=True)
        embed = discord.Embed(title="Успешно", color=bot.embed_color)
        description = ""
        description += f"> **Баланс**: `{res.value['balance']} RUB`\n"
        description += f"> **Потрачено**: `{res.value['spent']} RUB`\n"
        description += f"> **Куплено товаров**: `{res.value['bought']}`\n"
        embed.description = description
        await interaction.response.send_message(embed=embed)
    except:
        traceback.print_exc()

@bot.tree.command(name="create", description="Создать товар.", guild=panel)
async def create_command(interaction: discord.Interaction, name: str = None, description: str = None, price: str = None):
    return await interaction.response.send_message("`Обратитесь к MegaWatt_#1114 для создания какого-то товара.`\n`Обговорим цену.`")

@bot.tree.command(name = "ping", description="Задержка бота в миллисекундах.", guild=panel)
async def ping(interaction: discord.Interaction) -> None:
    await interaction.response.defer(thinking=True)
    ping1 = f"{str(round(bot.latency * 1000))}ms"
    embed = discord.Embed(title = "**Pong!**", color = 0xafdafc)
    tim = time.time()
    bot.db.fetch({}, "profiles")
    secs = round((time.time() - tim)*1000)
    embed.description = f'`Обработка команд:` **{ping1}**\n`База данных:` **{secs}ms**'
    await interaction.followup.send(embed = embed)

@bot.tree.command(name="remove_all_codes", description="Удаляет все коды из категории.", guild=panel)
async def remove_all_codes(interaction: discord.Interaction, category: str):
    try:
        if category in [x for _, _, x in bot.nitros]:
            await interaction.response.defer()
            codes = bot.db.fetch({}, category, mode=2)
            lenresvalue = len(codes.value if codes.value else [])
            if codes.status:
                bot.db.remove(codes.value, "all_codes")
            bot.db.remove({}, category)
            count = bot.db.fetch({}, "count").value
            bot.db.remove({}, "count")
            count[category] -= lenresvalue
            bot.db.add(count, "count")
            return await interaction.followup.send(f"Удалено {lenresvalue} кодов из категории {category}", ephemeral=True)
        return await interaction.response.send_message(f"Категория не найдена.", ephemeral=True)
    except Exception:
        traceback.print_exc()
@remove_all_codes.autocomplete("category")
async def set_autocomplete(interaction: discord.Interaction, current: str):
    return [app_commands.Choice(name=x, value=x) for x in dbCategories]

@bot.tree.command(name="set_price", description="Устанавливает цену на одну из категорий нитро.", guild=panel)
async def set_price(interaction: discord.Interaction, category: str, price: int) -> None:
    try:
        guild = interaction.client.get_guild(ADMIN_SERVER)
        role = discord.utils.get(guild.roles, id=ADMIN_ROLE)
        member = guild.get_member(interaction.user.id)
        if member is None or role not in member.roles:
            return await interaction.response.send_message("Вы не имеете права использовать эту команду!", ephemeral=True)
        await interaction.response.defer()
        bot.set_price(price=price, category=category)
        embed = discord.Embed(
            color = bot.embed_color,
            title= "Успешно",
            description= f"**Цена категории** `{category}` **установлена на** `{price} RUB`"
        )
        await interaction.followup.send(embed=embed)
    except Exception:
        traceback.print_exc()
@set_price.autocomplete("category")
async def set_autocomplete(interaction: discord.Interaction, current: str):
    return [app_commands.Choice(name=x, value=x) for x in [x for _, _, x in bot.nitros]]

@bot.event
async def on_ready():
    check_paid.start()
    print(f"Logged in as {bot.user.name}#{bot.user.discriminator}")
    print("--------------------------------------------------------")

async def main():
    async with bot:
        await bot.start(BOT_TOKEN)
asyncio.new_event_loop().run_until_complete(main())
#######################################################################################################################
