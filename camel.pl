#!/usr/bin/perl

$ENV{JAVA_HOME} = "/opt/homebrew/Cellar/openjdk@21/21.0.4/libexec/openjdk.jdk/Contents/Home";

my $endpoint = defined($ARGV[0]) ? shift(@ARGV) : "";

$vers = "4.10.1";
$dir = "camel-${vers}-branch";
$patchdir = "camelpatches";

$upstreambranch = "camel-$vers";
$currentprodbranch = "camel-4.10.0-branch";
$prodlocation = "prodlocation";

# Clean up directories
system("rm -rf $dir");
system("rm -rf $prodlocation");

# Clone
system("git clone git\@github.com:jboss-fuse/camel.git $dir");
system("git clone -b $currentprodbranch git\@github.com:jboss-fuse/camel.git $prodlocation");

#system("cp -r ~/prod/camel $prodlocation");

chdir $dir;
system("git remote add upstream git\@github.com:apache/camel.git");
system("git fetch upstream");
system("git fetch upstream --tags");

sleep(3);

system("git checkout -b camel-${vers}-branch $upstreambranch");

sleep(3);

# Change the version
system("export JAVA_HOME=/opt/homebrew/Cellar/openjdk\@21/21.0.4/libexec/openjdk.jdk/Contents/Home; /usr/local/apache-maven-3.9.9/bin/mvn -DnewVersion=${vers}-SNAPSHOT -DgenerateBackupPoms=false versions:set");

system("git commit -a -m \"Change versions to ${vers}-SNAPSHOT\"");

if ($endpoint =~ m|endbeforepre|) {
    print "ENDBEFOREPRE\n";
    exit(0);
}

# Apply pre-prod-maven-plugin patches, with check
open (FILEH, "ls ../$patchdir/pre-*.patch | sort -u |");
while ($file = <FILEH>) {
    chomp $file;

    print "\n\n\n==== APPLYING $file\n\n";
    system("git apply --check $file");
    system("git am --keep-cr --signoff < $file");
    print "====\n\n\n";
}
close(FILEH);

# Copy the entire product directory
system ("cp -r ../$prodlocation/product .");
system ("git add product");

sleep(3);

if ($endpoint =~ m|endbeforeplugin|) {
    print "ENDBEFOREPLUGIN\n";
    exit(0);
}

sleep(3);

system("export JAVA_HOME=/opt/homebrew/Cellar/openjdk\@21/21.0.4/libexec/openjdk.jdk/Contents/Home; /usr/local/apache-maven-3.9.9/bin/mvn org.l2x6.cq:cq-camel-prod-maven-plugin:camel-prod-excludes -N");

sleep(3);

system("git add .mvn/excludes.txt");
system("git commit -a -m \"Run prod-maven-plugin for the first time\"");

system("export JAVA_HOME=/opt/homebrew/Cellar/openjdk\@21/21.0.4/libexec/openjdk.jdk/Contents/Home; /usr/local/apache-maven-3.9.9/bin/mvn -DskipTests clean install");

sleep(3);

system("git commit -a -m \"Compile with results of prod-maven-plugin\"");

if ($endpoint =~ m|endbeforepost|) {
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
system("export JAVA_HOME=/opt/homebrew/Cellar/openjdk\@21/21.0.4/libexec/openjdk.jdk/Contents/Home; /usr/local/apache-maven-3.9.9/bin/mvn -DskipTests clean install");
