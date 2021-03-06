#!/usr/bin/env python                                                                                                                                                          

__author__ = "Molly Gibson"
__email__ = "molly.gibson@wustl.edu"


# Python imports
import argparse, subprocess, os, itertools, operator, re, sys
# Other imports
import parse_config, parse_mapping

def main():
    parser = argparse.ArgumentParser(description="This script annotates output from \
              antibiotic functional metagenomic selections assembled using PARFuMS.")

    # arguments
    parser.add_argument('-contigs', dest="contig_fp", help="Path to contig file from PARFuMS output")
    parser.add_argument('-proteins', dest="protein_fp", help="Path to protein file from PARFums output")
    parser.add_argument('--resfams', dest="use_resfams", help="Use the full Resfams profile HMM database", action='store_true', default=False)
    parser.add_argument('--resfams_only', dest="use_resfams_only", help="Use the Resfams-only profile HMM database", action='store_true', default=False)
    parser.add_argument('--no_ga', dest="no_ga", help="Do not use gathering thresholds for profile HMM annotation", action='store_true', default=False)
    parser.add_argument('--only_args', dest="only_args", help="Only annotate with one of the Resfams databases", action='store_true', default=False)
    parser.add_argument('-o', dest="output_fp", help="Path to output directory for annotation")
    parser.add_argument('-f', dest="override", help="Override all previous output in the designated output directory", action='store_true', default=False)
    parser.add_argument('-m', dest="mapping_fp", help="Mapping directory of sample name to antibiotic")
    parser.add_argument('-config', dest="config_fp", help="Path to config file that contains database location") 
    parser.add_argument('--prefix', dest="prefix",help="set prefix")
    args = parser.parse_args()
    
    # check to see that either contigs or proteins are provided
    if not args.contig_fp and not args.protein_fp:
        parser.exit(status=0, message="You must provide either contigs or proteins to annotate\nCheck usage with 'annotate_parfum_contigs.py -h'.\n\n")

    # make sure that you are only using one resfams database
    if args.use_resfams and args.use_resfams_only:
        parser.exit(status=0, message="You can only use one resfams database.\nCheck usage with 'annotate_parfum_contigs.py -h'.\n\n")

    # check to make sure that there are no spaces in headers
    if args.contig_fp:
        fasta_file = args.contig_fp
    elif args.protein_fp:
        fasta_file = args.protein_fp

    for line in open(fasta_file, 'r'):
        if line.startswith(">"):
            header = line.rstrip()
            if re.search(r"\s", header):
                sys.exit("You can not have white space in the header of your fasta file.")

    # check to see config file exists
    if args.config_fp:
	config_fp = args.config_fp
    else:
	parser.exit(status=0,message="You must provide the path to config file")

    # set the output path and make the directory
    if args.prefix:
	prefix = args.prefix
    elif args.contig_fp:
	prefix =  os.path.splitext(os.path.basename(args.contig_fp))[0] # Modified by Manish to extract just filename without extension, even if filepath is provided
        #prefix = os.path.splitext(args.contig_fp)[0]
    elif args.protein_fp:
        prefix = os.path.splitext(args.protein_fp)[0]
    

    if not args.output_fp:
        output_fp = prefix + "_annotation"
    else:
        output_fp = args.output_fp

    if not os.path.isdir(output_fp):
        subprocess.call('mkdir ' + output_fp, shell=True)

    # call orfs (if contigs) and annotate proteins
    if not args.protein_fp:
        protein_fp = call_orfs(args.contig_fp, output_fp, prefix, args, config_fp)
    else:
        protein_fp = args.protein_fp
    annotation_fp = annotate_proteins(protein_fp, output_fp, args, config_fp)
    

    # merge hmm files
    if (not os.path.isfile(output_fp + '/' + prefix + '.HMMAnnotation.txt') or args.override) and args.contig_fp:
        merge_hmm_files(output_fp, prefix, args)

    # process hmm files further
    if (not os.path.isfile(output_fp + '/' + prefix + '.HMMAnnotation.final.txt') or args.override) and args.contig_fp:
        process_hmm_file(output_fp, prefix, args)

#def parse_configfile(config_fp):

def call_orfs(contigs, output_fp, prefix, args, config_fp):    

    if not os.path.isfile(output_fp + '/sequence.gff') or args.override:
	print 'config = ' + parse_config.main(config_fp).mgm_model_fp
        command = 'gmhmmp -a -d -f G -m ' + parse_config.main(config_fp).mgm_model_fp + ' -o ' + output_fp + '/sequence.gff ' + contigs
        print command
	subprocess.call(command, shell=True)

    if not os.path.isfile(output_fp + '/nucleotides.fasta') or args.override:
        command = 'nt_from_gff.pl < ' + output_fp + '/sequence.gff > ' + output_fp + '/nucleotides.fasta'
        subprocess.call(command, shell=True)

    if not os.path.isfile(output_fp + '/proteins.fasta') or args.override:
        command = 'aa_from_gff.pl < ' + output_fp + '/sequence.gff > ' + output_fp + '/proteins.fasta'
        subprocess.call(command, shell=True)

    nucleotideFile = open(output_fp + '/nucleotides.fasta', 'r')
    newNucFile = open(output_fp + '/nucleotides_updated.fasta', 'w')
    finalNuc = open(output_fp + '/nucleotides_final.fasta', 'w')
    proteinFile = open(output_fp + '/proteins.fasta', 'r')
    sequenceFile = open(output_fp + '/sequence.gff', 'r')
    newProteinFilePath = output_fp + '/proteins_updated.fasta'
    newProteinFile = open(output_fp + '/proteins_updated.fasta', 'w')
    finalProtein = open(output_fp + '/proteins_final.fasta', 'w')
    contigNames = open(output_fp + '/contig_names.txt', 'w')
    
    for line in nucleotideFile:
        if line.startswith('>'):
            # Create new header                                                                                                                                                                                                                   
            header = line.strip('>').split('_')
            searchS = header[0] + '_' + header[1] + " " +  header[2]
            # Find the line in sequenceFile that contains searchS                                                                                                                                                                                 
            for headLine in sequenceFile:
                if not headLine.startswith('#'):
                    if searchS in headLine:
                        sequenceHeader = headLine
                        break
            headerPieces = sequenceHeader.split('\t')

            
            sample_name = headerPieces[0].split("_Contig_")[0]
	    #print sample_name

            if len(headerPieces[0].split("_Contig_")) > 1:
                contig_num = headerPieces[0].split("_Contig_")[1].split("_")[0]
            else:
                contig_num = "NA"

            if len(headerPieces[0].split("_Mean:")) > 1:
                mean = headerPieces[0].split("_Mean:")[1].split("_")[0]
            else:
                mean = "NA"

            if len(headerPieces[0].split("_Len:")) > 1:
                length = headerPieces[0].split("_Len:")[1]
            else:
                length = "NA"

            if args.mapping_fp:
		#print "sample_name => " + str(parse_mapping.main(args.mapping_fp).id[sample_name])
		#print "sample_name => " + sample_name + " contig_num => " + contig_num + ":" + headerPieces[3] + "-" + headerPieces[4]
                newHeader = ">" + sample_name + "." + contig_num + ":" +  headerPieces[3] + "-" + headerPieces[4] + " ID:" + str(parse_mapping.main(args.mapping_fp).id[sample_name]) + " Contig:" + contig_num + " Mean:" + mean + " Len:" + length  + " abx:" + str(parse_mapping.main(args.mapping_fp).abx[sample_name]) + " start:" + headerPieces[3] + " stop:" + headerPieces[4] + " orientation:" + headerPieces[6]
            else:
                newHeader = ">" + sample_name + "." + contig_num + ":" + headerPieces[3] + "-" + headerPieces[4] + " ID:" + sample_name + " Contig:" + contig_num + " Mean:" + mean + " Len:" + length  + " abx:NA" + " start:" + headerPieces[3] + " stop:" + headerPieces[4] + " orientation:" + headerPieces[6]
            finalNuc.write(newHeader + "\n")
            newNucFile.write(">" + headerPieces[0] + "_" + headerPieces[3] + "_" + headerPieces[4] + "_" + headerPieces[6] + "\n")
            contigNames.write(">" + headerPieces[0] + "_" + headerPieces[3] + "_" + headerPieces[4] + "_" + headerPieces[6] + "\n")
        else:
            finalNuc.write(line)
	    newNucFile.write(line)

    newNucFile.close()
    contigNames.seek(0)
    sequenceFile.seek(0)
    
    for line in proteinFile:
        if line.startswith('>'):
            # Create new header
            header = line.strip('>').split('_')
            searchS = header[0] + '_' + header[1] + " " +  header[2]
            # Find the line in sequenceFile that contains searchS
            for headLine in sequenceFile:
                if not headLine.startswith('#'):
                    if searchS in headLine:
                        sequenceHeader = headLine
                        break
            headerPieces = sequenceHeader.split('\t')

            sample_name = headerPieces[0].split("_Contig_")[0]

            if len(headerPieces[0].split("_Contig_")) >1:
                contig_num = headerPieces[0].split("_Contig_")[1].split("_")[0]
            else:
                contig_num = "NA"

            if len(headerPieces[0].split("_Mean:")) > 1:
                mean = headerPieces[0].split("_Mean:")[1].split("_")[0]
            else:
                mean = "NA"

            if len(headerPieces[0].split("_Len:")) > 1:
                length = headerPieces[0].split("_Len:")[1]
            else:
                length = "NA"

            if args.mapping_fp:
                newHeader = ">" + sample_name + "." + contig_num +  ":" + headerPieces[3] + "-" + headerPieces[4] + " ID:" + str(parse_mapping.main(args.mapping_fp).id[sample_name]) + " Contig:" + contig_num + " Mean:" + mean + " Len:" + length + " abx:" + str(parse_mapping.main(args.mapping_fp).abx[sample_name]) + " start:" + headerPieces[3] + " stop:" + headerPieces[4] + " orientation:" + headerPieces[6]
            else:
                newHeader = ">" + sample_name + "." + contig_num + ":" + headerPieces[3] + "-" + headerPieces[4] + " ID:" + sample_name + " Contig:" + contig_num + " Mean:" + mean + " Len:" + length  + " abx:NA" + " start:" + headerPieces[3] + " stop:" + headerPieces[4]+ " orientation:" + headerPieces[6]
            finalProtein.write(newHeader + "\n")
            newProteinFile.write(">" + headerPieces[0] + "_" + headerPieces[3] + "_" + headerPieces[4] + "_" + headerPieces[6] +  "\n")
            contigNames.write(">" + headerPieces[0] + "_" + headerPieces[3] + "_" + headerPieces[4] + "_" + headerPieces[6] + "\n")
        else:
            finalProtein.write(line)
            newProteinFile.write(line)
        
    newProteinFile.close()
    contigNames.close()

    return(newProteinFilePath)

# annotate proteins
def annotate_proteins(proteins,output_fp, args, config_fp):
    if (not os.path.isfile(output_fp + '/Pfam-targets.txt') or args.override) and not args.only_args:
        if args.no_ga:
            command = 'hmmscan -o /dev/null --tblout ' + output_fp + '/Pfam-targets.txt ' + parse_config.main(config_fp).pfam_database_fp + ' ' +  proteins
        else:
            command = 'hmmscan -o /dev/null --cut_ga --tblout ' + output_fp + '/Pfam-targets.txt ' + parse_config.main(config_fp).pfam_database_fp + ' ' +  proteins
        subprocess.call(command, shell=True)
    if (not os.path.isfile(output_fp + '/Tigrfam-targets.txt') or args.override) and not args.only_args:
        if args.no_ga:
            command = 'hmmscan -o /dev/null --tblout ' + output_fp + '/Tigrfam-targets.txt ' + parse_config.main(config_fp).tigrfam_database_fp + ' ' + proteins
        else:
            command = 'hmmscan -o /dev/null --cut_ga --tblout ' + output_fp + '/Tigrfam-targets.txt ' + parse_config.main(config_fp).tigrfam_database_fp + ' ' + proteins
        subprocess.call(command, shell=True)
    if not os.path.isfile(output_fp + '/Resfams-targets.txt') or args.override:
        if args.use_resfams:
            if args.no_ga:
                command = 'hmmscan -o /dev/null --tblout ' + output_fp + '/Resfams-targets.txt ' + parse_config.main(config_fp).resfam_database_fp + ' ' + proteins
            else:
                command = 'hmmscan -o /dev/null --cut_ga --tblout ' + output_fp + '/Resfams-targets.txt ' + parse_config.main(config_fp).resfam_database_fp + ' ' + proteins
            subprocess.call(command, shell=True)
        if args.use_resfams_only:
            if args.no_ga:
                command = 'hmmscan -o /dev/null --tblout ' + output_fp + '/Resfams-targets.txt ' + parse_config.main(config_fp).resfam_only_database_fp + ' ' + proteins
            else:
                command = 'hmmscan -o /dev/null --cut_ga --tblout ' + output_fp + '/Resfams-targets.txt ' + parse_config.main(config_fp).resfam_only_database_fp + ' ' + proteins
            subprocess.call(command, shell=True)

    # merge hmm annotations 

def merge_hmm_files(output_fp, prefix, args):
    if not args.only_args:
        pfam = open(output_fp + '/Pfam-targets.txt', 'r')
        tigrfam = open(output_fp + '/Tigrfam-targets.txt', 'r')

    if args.use_resfams or args.use_resfams_only:
        resfams = open(output_fp + '/Resfams-targets.txt', 'r')

    output = open(output_fp + '/' + prefix + '.HMMAnnotation.txt', 'w')
    contigs = open(output_fp + '/contig_names.txt', 'r') 

    for line in contigs:
        if not args.only_args:
            pfam.seek(0)
            tigrfam.seek(0)

        if args.use_resfams or args.use_resfams_only:
            resfams.seek(0)

        hits = []
        contig = line.strip(">").rstrip()

        if not args.only_args:
            # Process Pfam File
            for item in pfam:
                if contig in item:
                    pieces = item.rstrip().split()
                    description = pieces[18]
                    if len(pieces) > 19:
                        description = " ".join(pieces[18:len(pieces)])
                    array = ["Pfam", pieces[1], pieces[2], pieces[3], float(pieces[4]), float(pieces[5]), float(pieces[6]), float(pieces[7]), float(pieces[8]), float(pieces[9]), description, pieces[0]]
                    hits.append(array)

            # Process TIGRFam File                                                                                                                                                                                                         
            for item in tigrfam:
                if contig in item:
                    pieces = item.rstrip().split()
                    array = ["TIGRFam", pieces[1], pieces[2], pieces[3], float(pieces[4]), float(pieces[5]), float(pieces[6]), float(pieces[7]), float(pieces[8]), float(pieces[9]), " ".join(pieces[18:len(pieces)]), pieces[0] ]
                    hits.append(array)

        # Process ResFams Files                                                                                                                                                                                                            
        if args.use_resfams or args.use_resfams_only:
            for item in resfams:
                if contig in item:
                    pieces = item.rstrip().split()
                    if pieces[1].startswith('P'):
                        array = ["Resfam", pieces[1], pieces[2], pieces[3], float(pieces[4]), float(pieces[5]), float(pieces[6]), float(pieces[7]), float(pieces[8]), float(pieces[9]), " ".join(pieces[18:len(pieces)])]
                    elif pieces[1].startswith('T'):
                        array = ["Resfam", pieces[1], pieces[2], pieces[3], float(pieces[4]), float(pieces[5]), float(pieces[6]), float(pieces[7]), float(pieces[8]), float(pieces[9]), " ".join(pieces[18:len(pieces)])]
                    else:
                        array = ["Resfam", pieces[1], pieces[2], pieces[3], float(pieces[4]), float(pieces[5]), float(pieces[6]), float(pieces[7]), float(pieces[8]), float(pieces[9]), pieces[0]]
                    hits.append(array)

        output.write(line.rstrip() + "\n")

        final_list = []
        for item in hits:
            pieces = item[2].split('_')
            start = pieces[len(pieces)-3]
            stop = pieces[len(pieces)-2]
            final_list.append([start, stop, item[0], item[1], item[10], item[4], item[5]])

        pieces = contig.rstrip().split('_')

        output.write(pieces[len(pieces)-3] + "\t" + pieces[len(pieces)-2] + "\t" + pieces[len(pieces)-1] + "\n")

        sorted_hits = sorted(final_list, reverse=True,  key=lambda hit: hit[6])

        for key,group in itertools.groupby(sorted_hits,operator.itemgetter(6)):
            sorted_group = sorted(list(group), key=lambda hit: hit[5])

            for item in sorted_group:
                if item:
                    output.write("\t" + str(item[2]) + "\t" + str(item[3]) + "\t" + str(item[4]) + "\t" + str(item[5]) + "\t" + str(item[6]) + "\n")

def process_hmm_file(output_fp, prefix, args):
    hmm_annotations = open(output_fp + '/' + prefix + '.HMMAnnotation.txt', 'r')
    output = open(output_fp + '/' + prefix + '.HMMAnnotation.final.txt', 'w')
    tab_file = open(output_fp + '/' + prefix + '.HMMAnnotation.tab', 'w')

    tab_file.write("sample\tcontig\tcontig_num\tstart\tstop\tori\tdatabase\tanno_id\tdescription\teval\tbit_score\n")

    save_contig_name = ""
    no_annotation = False
    for line in hmm_annotations:
        if line.startswith(">"):
            headerPieces = line.strip(">").split("\t")
            sample_name = headerPieces[0].split("_Contig_")[0].rstrip()

            if len(headerPieces[0].split("_Contig_")) > 1:
                contig_num = headerPieces[0].split("_Contig_")[1].split("_")[0].rstrip()
            else:
                contig_num = "NA"

            if len(headerPieces[0].split("_Mean:")) > 1:
                mean = headerPieces[0].split("_Mean:")[1].split("_")[0].rstrip()
            else:
                mean = "NA"

            if len(headerPieces[0].split("_Len:")) > 1:
                length = headerPieces[0].split("_Len:")[1].rstrip()
            else:
                length = "NA"            

            start = line.split("_")[len(line.split("_"))-3]
            stop = line.split("_")[len(line.split("_"))-2]
            ori = line.split("_")[len(line.split("_"))-1]

            if args.mapping_fp:                                                                                                                                                                                                             
                contig_name = ">" + sample_name + " ID:" + str(parse_mapping.main(args.mapping_fp).id[sample_name]) + " Contig:" + contig_num + " Mean:" + mean + " Len:" + length + " abx:" + str(parse_mapping.main(args.mapping_fp).abx[sample_name]) 
            else:
                contig_name = ">" + sample_name + " ID:" + sample_name + " Contig:" + contig_num + " Mean:" + mean + " Len:" + length  + " abx:NA" 

            if not contig_name == save_contig_name:
                output.write(contig_name + "\n")
            save_contig_name = contig_name
            not_annotation = False
        elif not line.startswith("\t"):
            if no_annotation:
                output.write("\t\tMetaGeneMark\n")
                no_annotation = True
            output.write("\t" + line)

            start_stop = line.rstrip()
        else:
            output.write("\t\t" + line)
            tab_file.write(contig_name.split()[0].rstrip().strip('>') + "\t" + contig_name + "\t" + contig_num + "\t" + start_stop + line)
            no_annotation = False


if __name__ == "__main__":
    main()
    
