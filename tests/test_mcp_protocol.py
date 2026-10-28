import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_stdio_discovery_and_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            env={**os.environ,'PECVD_WORKSPACE':directory}
            params=StdioServerParameters(command=sys.executable,args=['-m','pecvd_mcp.server'],env=env)
            async with stdio_client(params) as (read,write):
                async with ClientSession(read,write) as session:
                    await session.initialize()
                    listing=await session.list_tools()
                    self.assertEqual(len(listing.tools),13)
                    baseline=await session.call_tool('read_paper_baseline',{})
                    self.assertFalse(baseline.isError)
                    data=json.loads(baseline.content[0].text)
                    self.assertEqual(data['reference']['reported']['rf_power_W'],600)
                    project=await session.call_tool('create_connection_project',{'project_id':'protocol_test','nr':22,'nz':4})
                    self.assertFalse(project.isError)
                    self.assertTrue((Path(directory)/'protocol_test/gap.msh').is_file())
                    blocked=await session.call_tool('read_project_text',{'project_id':'protocol_test','relative_path':'../../secret.txt'})
                    self.assertTrue(blocked.isError)
                    no_solver=await session.call_tool('iterate_connection_test',{'project_id':'protocol_test','iterations':1})
                    self.assertTrue(no_solver.isError)


if __name__=='__main__':unittest.main()
