#!/usr/bin/perl

$ENV{JAVA_HOME} = "/opt/homebrew/Cellar/openjdk@21/21.0.4/libexec/openjdk.jdk/Contents/Home";

my $endpoint = defined($ARGV[0]) ? shift(@ARGV) : "";

$vers = "4.10.2";
$dir = "camel-spring-boot-${vers}-branch";
$patchdir = "csbpatches";

$upstreambranch = "camel-spring-boot-$vers";
$currentprodbranch = "camel-spring-boot-4.10.1-branch";
$prodlocation = "csbprodlocation";

# Clean up directories
system("rm -rf $dir");
system("rm -rf $prodlocation");

# Clone
system("git clone git\@github.com:jboss-fuse/camel-spring-boot.git $dir");
system("git clone -b $currentprodbranch git\@github.com:jboss-fuse/camel-spring-boot.git $prodlocation");

#system("cp -r ~/prod/camel-spring-boot $prodlocation");

chdir $dir;
system("git remote add upstream git\@github.com:apache/camel-spring-boot.git");
system("git fetch upstream");
system("git fetch upstream --tags");

sleep(10);

system("git checkout -b camel-spring-boot-${vers}-branch $upstreambranch");

sleep(3);

# Change the version
system("export JAVA_HOME=/opt/homebrew/Cellar/openjdk\@21/21.0.4/libexec/openjdk.jdk/Contents/Home; /usr/local/apache-maven-3.9.9/bin/mvn -DnewVersion=${vers}-SNAPSHOT -DgenerateBackupPoms=false versions:set");

system("git commit -a -m \"Change versions to ${vers}-SNAPSHOT\"");

system("cp ../csb-rewrite.yml ./rewrite.yml");
system("export JAVA_HOME=/opt/homebrew/Cellar/openjdk\@21/21.0.4/libexec/openjdk.jdk/Contents/Home; /usr/local/apache-maven-3.9.9/bin/mvn -N -U org.openrewrite.maven:rewrite-maven-plugin:run -Drewrite.activeRecipes=com.redhat.camel-spring-boot.AddProductBranchProperties");

if ($endpoint =~ m|endbeforepre|) {
    exit(0);
}

# Apply pre-prod-maven-plugin patches, with check
#open (FILEH, "ls ../$patchdir/pre-*.patch | sort -u |");
#while ($file = <FILEH>) {
#    chomp $file;

#    print "\n\n\n==== APPLYING $file\n\n";
#    system("git apply --check $file");
#    system("git am --keep-cr --signoff < $file");
#    print "====\n\n\n";

#}
#close(FILEH);

# Copy the entire product directory
system ("cp -r ../$prodlocation/product .");
system ("git add product");

sleep(3);

# Copy the entire sap directory
system ("cp -r ../$prodlocation/sap .");
system ("git add sap");

# Copy the entire cics directory
system ("cp -r ../$prodlocation/cics .");
system("git add cics");

system("export JAVA_HOME=/opt/homebrew/Cellar/openjdk\@21/21.0.4/libexec/openjdk.jdk/Contents/Home; /usr/local/apache-maven-3.9.9/bin/mvn org.l2x6.cq:cq-camel-spring-boot-prod-maven-plugin:camel-spring-boot-prod-excludes -N");

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

    print "\n\n\n==== APPLYING $file\n\n";
    system("git apply --check $file");
    system("git am --keep-cr --signoff < $file");
    print "====\n\n\n";

}
close(FILEH);

sleep(3);

# Apply tooling changes
system ("cp -r ../$prodlocation/tooling/redhat-camel-spring-boot-bom-generator ./tooling");
system ("cp -r ../$prodlocation/tooling/redhat-camel-spring-boot-bom ./tooling");
system ("cp -r ../$prodlocation/tooling/redhat-patch-maven-plugin ./tooling");

sleep(3);

system ("git add tooling");

sleep(3);

system("git commit -a -m \"Compile with results of prod-maven-plugin\"");



# Build for final time - there should be no changes 
system("export JAVA_HOME=/opt/homebrew/Cellar/openjdk\@21/21.0.4/libexec/openjdk.jdk/Contents/Home; /usr/local/apache-maven-3.9.9/bin/mvn -DskipTests clean install");

system("git commit -a -m \"Build and refresh tooling\"");
