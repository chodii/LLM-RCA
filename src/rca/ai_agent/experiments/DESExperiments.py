# -*- coding: utf-8 -*-

"""

Created on Fri Apr 24 16:00:35 2026



@author: chodo

"""



import os, sys




from rca.data_preprocessing.evaluation_set import IssueLoader

from rca.ai_agent.experiments import evaluate_IR

from rca.ai_agent.experiments import coverage_analysis

from rca.results import Logger



from rca.ai_agent.agent import DESAI

from rca.ai_agent.agent import message_manager

import argparse





def coverage_analysis_api(incidents_json, chunking):

    if chunking is None:

        tag = "windowed_selection/"

    else:

        tag = "chunked_"+str(chunking)+"/"

    dest = "out/"+tag

    coverage_analysis.api(incidents_json, chunking, dest, tag)

    



def api(context_manager, incidents_json, chunk_size ,model, VALIDATION=False):

    #incident=None

    #incidents_json=r".\DataPreprocessing\out\chunked_incidents.json"

    tag = "chunked_"+str(chunk_size)+"/"

    dest = "out/"+tag

    evaluator = evaluate_IR.ExperimentsEvaluator()

    if VALIDATION:

        res_name = "-VALIDATION_results.json"

        print("Running validation")

    else:

        res_name = "-EXPERIMENT_results.json"

        print("Running experimentation")

    logger = Logger.logger(dest=dest, tag=res_name)

    for i, incident in enumerate(IssueLoader.load_incidents(incidents_json=incidents_json

                                                            , chunk_size=chunk_size

                                                            , OUT=dest)):

        #print(i)

        imod5=i % 5 != 0

        if (VALIDATION and imod5) or ((not VALIDATION) and (not imod5)):

            continue

        print("\n",i, incident)

        incident.swap_into_db()# (yyyy-mm-ddThh:mm:ss+hh:ss)

        print()

        TIME_ANCHOR = "This incident occured around (yyyy-mm-dd):"+str(incident.ts).split("T")[0]+"\n"

        user_problem = TIME_ANCHOR+incident.description

        rca, retrieved, rounds, _convers = DESAI.api(user_problem=user_problem

                           , context_manager=context_manager

                           , model=model)

        rca = rca["content"]

        logger.log(incident=incident, rca=rca, retrieved=retrieved, conversation=_convers)

        evaluator.evaluate(incident, rca, retrieved, rounds)

    evaluator.log_results(logger.res_folder, res_name)





def parse_args():

    parser = argparse.ArgumentParser(

       description="Experiment setup"

       )

    parser.add_argument(

        "-t", "--trunk",

        dest="trunk",

        action="store_true",

        help="Truncation context management strategy"

    )

    parser.add_argument(

         "-s", "--summarization",

         dest="summarization",

         action="store_true",

         help="Summarization context management strategy"

     )

    parser.add_argument(

         "-i", "--incidents",

         dest="incidents",

         default="chunked_incidents.json"

         ,help="The chunked_incidents.json file"

     )

    parser.add_argument(

         "-m", "--model",

         dest="model",

         default="openai/gpt-4o-mini"

         ,help="The model to be used"

     )

    parser.add_argument(

          "-a", "--target_analysis",

          dest="target_analysis",

          action="store_true",

          help="Target analysis instead of experiments"

      )

    parser.add_argument(

          "-v", "--validation",

          dest="validation",

          action="store_true",

          help="Validation set experimentation"

      )

    

    args = parser.parse_args()

    if args.summarization:

        context_manager = message_manager.ContextManagement.SUMMARIZATION

    elif args.trunk:

        context_manager = message_manager.ContextManagement.TRUNCATION

    else:

        context_manager = message_manager.ContextManagement.NONE

    return context_manager, args.incidents, args.target_analysis, args.validation, args.model



if __name__ == "__main__":

    context_manager, incidents_json, target_analysis, validation, model = parse_args()

    chunk_size = incidents_json.replace("\\","/").split("/")[-2]

    if not target_analysis:

        api(context_manager=context_manager, incidents_json=incidents_json, chunk_size=chunk_size,model=model, VALIDATION=validation)

    else:

        if not chunk_size.isdigit():

            chunk_size = None

        coverage_analysis_api(incidents_json, chunking=chunk_size)