package main

import (
	"archive/tar"
	//"bytes"
	//"encoding/json"
	"flag"
	"fmt"
	"github.com/go-logr/logr"
	"github.com/google/go-containerregistry/pkg/authn"
	//"github.com/kubernetes-sigs/kernel-module-management/internal/registry"
	"github.com/google/go-containerregistry/pkg/crane"
	v1 "github.com/google/go-containerregistry/pkg/v1"
	"io"
	//"io/fs"
	"k8s.io/klog/v2/klogr"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

func checkArg(arg *string, varname string, fallback string) {
	if *arg == "" {
		if fallback != "" {
			*arg = fallback
		} else {
			fmt.Printf("%s not found:\n", varname)
			flag.PrintDefaults()
			os.Exit(0)
		}
	}
}

/*
** Convert a relative path to an absolute path
** filenames in image manifests are normally relative but can be "path/file" or "./path/file"
** or occasionaly be absolute "/path/file" (in baselayers) depending on how they were created.
** and we need to turn them into absolute paths for easy string comparisons against the
** filesToSign list we've been passed from the CR via the cli
** the easiest way to do this is force it to be abs, then clean it up
 */
func canonicalisePath(path string) string {
	return filepath.Clean("/" + path)
}

func analyseKmod(extractionDir string, kernels []string, kmodsToAnalyse map[string]string, longReport bool) error {
	var args []string
	logger.Info("running analysis")
	//var args []string
	//args = append(args, "-s", "-f", extractionDir + "/ksc-report.txt" )
	args = append(args, "-f", extractionDir+"/ksc-report.txt")
	if longReport == false {
		args = append(args, "-r", "summary")
	} else {
		args = append(args, "-r", "full")
	}
	for _, kmod := range kmodsToAnalyse {
		args = append(args, "-m", kmod)
	}

	//fmt.Println("symvers", symvers)
	for _, s := range kernels {
		//fmt.Println("symvers s=", s)
		args = append(args, "-k", s)
	}
	/*
		./ksc_reporter.py
			-m ../simple-kmod/simple-procfs-kmod.ko
			-f ./ksc_report.txt
			-k 4.18.0-372.32.1.el8_6.x86_64
	*/
	logger.Info("running analysis", "command", "./analyse_kmod.py "+strings.Join(args, " "))
	out, err := exec.Command("./ksc_reporter.py", args...).Output()
	//cmd := exec.Command("./analyse_kmod.py", args...)
	//if err := cmd.Run(); err != nil {
	//	return fmt.Errorf("error running /analyse_kmod.py returned error: %v\n", err)
	//}
	//out, err := cmd.Output()
	if err != nil {
		return fmt.Errorf("error running /analyse_kmod.py returned error: %v\n", err)
	}
	fmt.Printf("\n%s\n", out)

	return nil
}

func die(exitval int, message string, err error) {
	fmt.Fprintf(os.Stderr, "\n%s\n", message)
	logger.Info("ERROR "+message, "err", err)
	logger.Error(err, message)
	os.Exit(exitval)
}

func ExtractBytesFromTar(size int64, tarreader io.Reader) ([]byte, error) {

	contents := make([]byte, size)
	offset := 0
	for {
		rc, err := tarreader.Read(contents[offset:])
		if err != nil && err != io.EOF {
			return nil, fmt.Errorf("could not read from tar: %v ", err)
		}
		offset += rc
		if err == io.EOF {
			break
		}
	}
	return contents, nil
}

func ExtractFileToFile(destination string, header *tar.Header, tarreader io.Reader) error {

	contents, err := ExtractBytesFromTar(header.Size, tarreader)
	if err != nil {
		return fmt.Errorf("could not read file %s: %v", destination, err)
	}

	dirname := filepath.Dir(destination)

	// I hope you've set your umask to something sensible!
	err = os.MkdirAll(dirname, 0770)
	if err != nil {
		return fmt.Errorf("could not create directory structure for %s: %v", destination, err)
	}
	err = os.WriteFile(destination, contents, 0700)
	if err != nil {
		return fmt.Errorf("could not create temp %s: %v", destination, err)
	}
	return nil

}

func extractFile(filename string, header *tar.Header, tarreader io.Reader, data []interface{}) error {

	extractionDir := data[0].(string)
	kmodsFound := data[1].(map[string]string)

	//canonfilename := canonicalisePath(filename)
	if len(filename) < 3 {
		return nil
	}
	if filename[len(filename)-3:] != ".ko" {
		return nil
	}
	canonfilename := filepath.Base(filename)

	//either the kmod has not yet been found, or we didn't define a list to search for
	//fmt.Printf("canonfilename=%s\n", canonfilename)
	if kmodsFound[canonfilename] == "" {
		logger.Info("Found kmod", "kmod", canonfilename, "matches kmod in image", header.Name)
		//its a file we wanted and haven't already seen
		//extract to the local filesystem
		err := ExtractFileToFile(extractionDir+"/"+canonfilename, header, tarreader)
		if err != nil {
			return err
		}
		kmodsFound[canonfilename] = extractionDir + "/" + canonfilename
		logger.Info("Extracted kmod", "kmod", canonfilename)

		return nil

	}
	return nil
}

func GetImageByName(imageName string, kc authn.Keychain, insecure bool, skipTLSVerify bool) (v1.Image, error) {
	options := []crane.Option{}

	if insecure {
		options = append(options, crane.Insecure)
	}

	if skipTLSVerify {
		rt := http.DefaultTransport.(*http.Transport).Clone()
		rt.TLSClientConfig.InsecureSkipVerify = true
		options = append(
			options,
			crane.WithTransport(rt),
		)
	}

	options = append(
		options,
		crane.WithAuthFromKeychain(kc),
	)

	img, err := crane.Pull(imageName, options...)
	if err != nil {
		return nil, fmt.Errorf("could not get image: %v", err)
	}

	return img, nil
}

func WalkFilesInImage(image v1.Image, fn func(filename string, header *tar.Header, tarreader io.Reader, data []interface{}) error, data ...interface{}) error {
	layers, err := image.Layers()
	if err != nil {
		return fmt.Errorf("could not get the layers from the fetched image: %v", err)
	}
	for i := len(layers) - 1; i >= 0; i-- {
		currentlayer := layers[i]

		layerreader, err := currentlayer.Uncompressed()
		if err != nil {
			return fmt.Errorf("could not get layer: %v", err)
		}

		/*
		** call fn on all the files in the layer
		 */
		tarreader := tar.NewReader(layerreader)
		for {
			header, err := tarreader.Next()
			if err == io.EOF || header == nil {
				break // End of archive
			}
			err = fn(header.Name, header, tarreader, data)
			if err != nil {
				return fmt.Errorf("died processing file %s: %v", header.Name, err)
			}
		}
	}

	return err
}

var logger logr.Logger

func main() {
	// get the env vars we are using for setup, or set some sensible defaults
	var err error
	var imageName string
	var extractionDir string
	var kernel string
	var longReport bool
	var quiet bool
	var insecure bool
	var skipTlsVerify bool

	logger = klogr.New().V(0)

	flag.StringVar(&imageName, "image", "", "name of the image to sign")
	flag.StringVar(&kernel, "kernel", "", "colon seperated list of kernels to test against")
	flag.BoolVar(&longReport, "long", false, "produce a long form report")
	flag.BoolVar(&quiet, "quiet", false, "supress log messages")
	flag.BoolVar(&insecure, "insecure", false, "images can be pulled from an insecure (plain HTTP) registry")
	flag.BoolVar(&skipTlsVerify, "skip-tls-verify", false, "do not check TLS certs on pull")

	flag.Parse()
	if quiet {
		logger = logger.V(5)
	}

	checkArg(&imageName, "image", "")
	// if we've made it this far the arguments are sane

	// get a temp dir to copy kmods into for signing
	extractionDir, err = os.MkdirTemp("/tmp/", "kmod_signer")
	if err != nil {
		die(1, "could not create temp dir", err)
	}
	//defer os.RemoveAll(extractionDir)

	kernelList := strings.Split(kernel, ":")
	//make a map of the files to sign so we can track what we want to sign
	kmodsToAnalyse := make(map[string]string)
	a := authn.DefaultKeychain

	img, err := GetImageByName(imageName, a, insecure, skipTlsVerify)
	if err != nil {
		die(3, "could not get Image()", err)
	}

	logger.Info("Successfully pulled image", "image", imageName)

	/*
	** loop through all the layers in the image from the top down
	 */
	err = WalkFilesInImage(img, extractFile, extractionDir, kmodsToAnalyse)
	if err != nil {
		die(9, "failed to search image", err)
	}

	analyseKmod(extractionDir, kernelList, kmodsToAnalyse, longReport)

}
