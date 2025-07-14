#!/usr/bin/perl

$ENV{JAVA_HOME} = "/opt/homebrew/Cellar/openjdk@17/17.0.14/libexec/openjdk.jdk/Contents/Home";

my $endpoint = defined($ARGV[0]) ? shift(@ARGV) : "";

$vers = "4.10.6";
$dir = "camel-kamelets-${vers}-branch";
$patchdir = "kameletpatches";

$currentprodbranch = "camel-kamelets-4.10.3-branch";
$prodlocation = "kameletprodlocation";

# Clean up directories
system("rm -rf $dir");
system("rm -rf $prodlocation");

# Clone
system("git clone git\@github.com:jboss-fuse/camel-kamelets.git $dir");
system("git clone  -b $currentprodbranch git\@github.com:jboss-fuse/camel-kamelets.git $prodlocation");

chdir $dir;
system("git remote add upstream git\@github.com:apache/camel-kamelets.git");
system("git fetch upstream");
system("git fetch upstream --tags");

sleep(3);

system("git checkout -b ${dir} v${vers}");

sleep(3);

# Change the version
system("export JAVA_HOME=/opt/homebrew/Cellar/openjdk\@17/17.0.14/libexec/openjdk.jdk/Contents/Home; /usr/local/apache-maven-3.9.9/bin/mvn -DnewVersion=${vers}-SNAPSHOT -DgenerateBackupPoms=false versions:set");

system("git commit -a -m \"Change versions to ${vers}-SNAPSHOT\"");

if ($endpoint =~ m|endbeforedelete|) {
    print "ENDBEFOREDELETE\n";
    exit(0);
}

print "Deleting unsupported files...\n";
open (DELETEH, "../$patchdir/files.delete");
while ($line = <DELETEH>) {
    chomp $line;
    system("git rm $line");
}
close(DELETEH);

sleep(3);
system("git commit -a -m\"Delete unsupported files\"");

if ($endpoint =~ m|endbeforepre|) {
    print "ENDBEFOREPRE\n";
    exit(0);
}

system("export JAVA_HOME=/opt/homebrew/Cellar/openjdk\@17/17.0.14/libexec/openjdk.jdk/Contents/Home; /usr/local/apache-maven-3.9.9/bin/mvn -DskipTests clean install");

sleep(3);

system("git commit -a -m\"Refresh\"");

sleep(3);


if ($endpoint =~ m|endbeforepost|) {
    print "ENDBEFOREPOST\n";
    exit(0);
}

# Apply post-prod-maven-plugin patches, with check
open (FILEH, "ls ../$patchdir/post-*.patch | sort -u |");
while ($file = <FILEH>) {
    chomp $file;

    system("git apply --check $file");
    system("git am --keep-cr --signoff < $file")

}
close(FILEH);

sleep(3);

# Build for final time - there should be no changes 
system("export JAVA_HOME=/opt/homebrew/Cellar/openjdk\@17/17.0.14/libexec/openjdk.jdk/Contents/Home; /usr/local/apache-maven-3.9.9/bin/mvn -DskipTests clean install");

print "gsed -i -e 's/camel.apache.org\\\/provider: \"Apache Software Foundation\"/camel.apache.org\\\/provider: \"Red Hat\"/g' \$(find . -type f)\n";
system("gsed -i -e 's/camel.apache.org\\\/provider: \"Apache Software Foundation\"/camel.apache.org\\\/provider: \"Red Hat\"/g' \$(find . -type f)");

system("git commit -a -m\"RHBAC-70 - Kamelets Catalog: Change metadata to reflect Red Hat catalog\"");

system("export JAVA_HOME=/opt/homebrew/Cellar/openjdk\@17/17.0.14/libexec/openjdk.jdk/Contents/Home; /usr/local/apache-maven-3.9.9/bin/mvn -DskipTests clean install");
