import sys

from app.batches.jobs.StockBuyCheckJob import StockBuyCheckJob
from app.batches.jobs.StockCodeMasterJob import StockCodeMasterJob
from app.batches.jobs.StockSellCheckJob import StockSellCheckJob
from app.config.database import dbConn
from app.batches.services.stockService import StockService
from app.batches.services.userService import UserService

session = dbConn.get_session()
userServiceImpl = UserService()
stockServiceImpl = StockService()

def test(name):
    """
     test for batch job
    """
    job = None
    if name == 'StockBuyCheckJob':
        job = StockBuyCheckJob()
    elif name == 'StockCodeMasterJob':
        job = StockCodeMasterJob()
    elif name == 'StockSellCheckJob':
        job = StockSellCheckJob()
    else:
        job = None

    if job is not None:
        job.process()




if __name__ == '__main__':
    args = sys.argv[1:]
    job_name = args.pop(0)

    if job_name is None or job_name == '':
        SystemExit('please input the job name')
    else:
        test(job_name)
