"""This is a cog for a discord.py bot.
It will add the run command for everyone to use

Commands:
    run            Run code using the Piston API

"""
# pylint: disable=E0402
import typing
import json
from discord import Embed, errors as discord_errors
from discord.ext import commands
from discord.utils import escape_mentions
from .utils.codeswap import add_boilerplate

# DEBUG = True


class Run(commands.Cog, name='CodeExecution'):
    def __init__(self, client):
        self.client = client
        self.languages = {
            'asm': 'nasm',
            'awk': 'awk',
            'bash': 'bash',
            'bf': 'brainfuck',
            'brainfuck': 'brainfuck',
            'c': 'c',
            'c#': 'csharp',
            'c++': 'cpp',
            'cpp': 'cpp',
            'cs': 'csharp',
            'csharp': 'csharp',
            'duby': 'ruby',
            'el': 'emacs',
            'elisp': 'emacs',
            'emacs': 'emacs',
            'elixir': 'elixir',
            'go': 'go',
            'java': 'java',
            'javascript': 'javascript',
            'jl': 'julia',
            'julia': 'julia',
            'js': 'javascript',
            'kotlin': 'kotlin',
            'nasm': 'nasm',
            'node': 'javascript',
            'php': 'php',
            'php3': 'php',
            'php4': 'php',
            'php5': 'php',
            'py': 'python3',
            'py3': 'python3',
            'python': 'python3',
            'python2': 'python2',
            'python3': 'python3',
            'r': 'r',
            'rb': 'ruby',
            'ruby': 'ruby',
            'rs': 'rust',
            'rust': 'rust',
            'sage': 'python3',
            'swift': 'swift',
            'ts': 'typescript',
            'typescript': 'typescript',
        }
        self.last_run_command_msg = dict()
        self.last_run_outputs = dict()

    async def get_api_response(self, ctx, language):
        message = [s.strip() for s in ctx.message.content.replace('```', '```\n').split('```')]

        if len(message) != 3:
            raise commands.BadArgument('No code or invalid code present')

        if language not in self.languages:
            language = message[1].split()[0]
            if language not in self.languages:
                raise commands.BadArgument(f'Unsupported language: {language}')

        args = [x for x in message[0].split('\n')[1:] if x]
        if message[1].startswith(language):
            source = message[1].lstrip(language).strip()
        else:
            source = message[1].strip()
        source = add_boilerplate(language, source)

        if not source:
            raise commands.BadArgument(f'No source code found')

        language = self.languages[language]
        data = {'language': language, 'source': source, 'args': args}
        headers = {'Authorization': self.client.config["emkc_key"]}

        # Call piston API
        # if DEBUG:
        #     await ctx.send('```DEBUG:\nSending Source to Piston\n' + str(data) + '```')
        async with self.client.session.post(
            'https://emkc.org/api/v1/piston/execute',
            headers=headers,
            data=json.dumps(data)
        ) as response:
            r = await response.json()
        if not response.status == 200:
            raise commands.CommandError(f'ERROR calling Piston API. {response.status}')
        if r['output'] is None:
            raise commands.CommandError(f'ERROR calling Piston API. No output received')

        output = escape_mentions('\n'.join(r['output'].split('\n')[:30]))
        if len(output) > 1945:
            output = output[:1945] + '[...]'

        # Logging
        logging_data = {
            'server': ctx.guild.name if ctx.guild else 'DMChannel',
            'server_id': str(ctx.guild.id) if ctx.guild else '0',
            'user': f'{ctx.author.name}#{ctx.author.discriminator}',
            'user_id': str(ctx.author.id),
            'language': language,
            'source': source
        }
        # if DEBUG:
        # await ctx.send('```DEBUG:\nSending Log\n' + str(logging_data) + '```')

        async with self.client.session.post(
            'https://emkc.org/api/internal/piston/log',
            headers=headers,
            data=json.dumps(logging_data)
        ) as response:
            if response.status != 200:
                await self.client.log_error(
                    commands.CommandError(f'Error sending log. Status: {response.status}'),
                    ctx
                )

        return (
            f'Here is your output {ctx.author.mention}\n'
            + '```\n'
            + output
            + '```'
        )

    async def send_howto(self, ctx):
        languages = sorted(set(self.languages.values()))

        run_instructions = (
            '**Here are my supported languages:**\n'
            + ', '.join(languages) +
            '\n\n**You can run code like this:**\n'
            '/run <language>\ncommand line parameters (optional) - 1 per line\n'
            '\\`\\`\\`\nyour code\n\\`\\`\\`\n'
            '\n**Provided by the EngineerMan Discord Server:**\n'
            'visit -> **emkc.org/run** to get it in your own server\n'
            'visit -> **discord.gg/engineerman** for more info\n'
            'visit -> **https://top.gg/bot/730885117656039466** and vote if you found this bot helpful'
        )

        e = Embed(title='I can execute code right here in Discord! (click here for instructions)',
                  description=run_instructions,
                  url='https://github.com/engineer-man/piston-bot#how-to-use',
                  color=0x2ECC71)

        await ctx.send(embed=e)

    @commands.command()
    async def run(self, ctx, language: typing.Optional[str] = None):
        """Run some code
        Type "/run" for instructions"""
        await ctx.trigger_typing()
        if not language or '```' not in ctx.message.content:
            await self.send_howto(ctx)
            return
        api_response = await self.get_api_response(ctx, language)
        msg = await ctx.send(api_response)
        self.last_run_command_msg[ctx.author.id] = ctx.message
        self.last_run_outputs[ctx.author.id] = msg

    @commands.command(hidden=True)
    async def edit_last_run(self, ctx, language: typing.Optional[str] = None):
        """Run some edited code"""
        if not ctx.invoked_with == 'run':
            return
        if not language:
            return
        try:
            msg_to_edit = self.last_run_outputs[ctx.author.id]
            api_response = await self.get_api_response(ctx, language)
            await msg_to_edit.edit(content=api_response)
        except KeyError:
            return
        except discord_errors.NotFound:
            return
        except Exception as e:
            msg_to_edit = self.last_run_outputs[ctx.author.id]
            await msg_to_edit.edit(content=self.client.error_string)
            raise e

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if after.author.bot:
            return
        if before.author.id not in self.last_run_command_msg:
            return
        if before.id != self.last_run_command_msg[before.author.id].id:
            return
        content = after.content.lower()
        prefixes = await self.client.get_prefix(after)
        if isinstance(prefixes, str):
            prefixes = [prefixes, ]
        if not any(content.startswith(f'{prefix}run') for prefix in prefixes):
            return
        ctx = await self.client.get_context(after)
        if ctx.valid:
            await self.client.get_command('edit_last_run').invoke(ctx)


def setup(client):
    client.add_cog(Run(client))
